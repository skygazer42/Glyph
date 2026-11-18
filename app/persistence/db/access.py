"""Database access with one explicit owner for connections and cursors."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from contextlib import closing
from functools import wraps
from threading import RLock
from typing import Any, Concatenate, ParamSpec, TypeVar
from urllib.parse import urlparse

import pandas as pd
import pymysql.cursors
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

P = ParamSpec("P")
R = TypeVar("R")


def _serialized(method: Callable[Concatenate[DBAccess, P], R]) -> Callable[Concatenate[DBAccess, P], R]:
    """Keep connection replacement, queries and shutdown in one serial scope."""
    @wraps(method)
    def call(self: DBAccess, *args: P.args, **kwargs: P.kwargs) -> R:
        with self._connection_lock:
            return method(self, *args, **kwargs)
    return call


class DBAccess:
    def __init__(self, dialect: str = "MySQL") -> None:
        self._connection_lock = RLock()
        self.dialect = dialect
        self._run_sql: Callable[[str], pd.DataFrame] | None = None
        self._close_connection: Callable[[], None] | None = None

    @_serialized
    def close(self) -> None:
        """Release the owned connection once; borrowed adapters are closed by their owner."""
        close_connection = self._close_connection
        self._close_connection = None
        self._run_sql = None
        if close_connection is not None:
            close_connection()

    @staticmethod
    def _query_frame(connection: Any, sql: str) -> pd.DataFrame:
        with closing(connection.cursor()) as cursor:
            cursor.execute(sql)
            return pd.DataFrame(cursor.fetchall(), columns=[column[0] for column in cursor.description])

    @_serialized
    def connect_to_postgres(
        self, host: str | None = None, dbname: str | None = None,
        user: str | None = None, password: str | None = None,
        port: int | None = None, **kwargs: Any,
    ) -> None:
        import psycopg2

        host = os.getenv("HOST") if host is None else host
        dbname = os.getenv("DATABASE") if dbname is None else dbname
        user = os.getenv("PG_USER") if user is None else user
        password = os.getenv("PASSWORD") if password is None else password
        configured_port = os.getenv("PORT") if port is None else port
        if not host or not dbname or not user or password is None or configured_port is None:
            raise ValueError("Please set your postgres host, database, user, password and port")
        self.close()
        connection = psycopg2.connect(
            host=host, dbname=dbname, user=user, password=password,
            port=int(configured_port), **kwargs,
        )

        def run_sql(sql: str) -> pd.DataFrame:
            try:
                return self._query_frame(connection, sql)
            except Exception:
                connection.rollback()
                raise

        self._close_connection = connection.close
        self._run_sql = run_sql
        self.dialect = "PostgreSQL"

    @_serialized
    def connect_to_mysql(
        self, host: str | None = None, dbname: str | None = None,
        user: str | None = None, password: str | None = None,
        port: int | None = None, **kwargs: Any,
    ) -> None:
        host = os.getenv("HOST") if host is None else host
        dbname = os.getenv("DATABASE") if dbname is None else dbname
        user = os.getenv("USER") if user is None else user
        password = os.getenv("PASSWORD") if password is None else password
        configured_port = os.getenv("PORT") if port is None else port
        if not host or not dbname or not user or password is None or configured_port is None:
            raise ValueError("Please set your MySQL host, database, user, password and port")
        self.close()
        connection = pymysql.connect(
            host=host, database=dbname, user=user, password=password,
            port=int(configured_port), cursorclass=pymysql.cursors.DictCursor, **kwargs,
        )

        def run_sql(sql: str) -> pd.DataFrame:
            try:
                connection.ping(reconnect=True)
                return self._query_frame(connection, sql)
            except Exception:
                connection.rollback()
                raise

        self._close_connection = connection.close
        self._run_sql = run_sql
        self.dialect = "MySQL"

    @_serialized
    def connect_to_oracle(
        self, user: str | None = None, password: str | None = None,
        dsn: str | None = None, **kwargs: Any,
    ) -> None:
        import oracledb

        user = os.getenv("USER") if user is None else user
        password = os.getenv("PASSWORD") if password is None else password
        dsn = os.getenv("DSN") if dsn is None else dsn
        if not dsn or not user or password is None:
            raise ValueError("Please set your Oracle dsn, user and password")
        self.close()
        connection = oracledb.connect(user=user, password=password, dsn=dsn, **kwargs)

        def run_sql(sql: str) -> pd.DataFrame:
            try:
                # Oracle rejects a trailing semicolon in driver query text.
                return self._query_frame(connection, sql.rstrip().removesuffix(";"))
            except Exception:
                connection.rollback()
                raise

        self._close_connection = connection.close
        self._run_sql = run_sql
        self.dialect = "Oracle"

    @_serialized
    def connect_to_bigquery(
        self, cred_file_path: str | None = None, project_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        from google.cloud import bigquery
        from google.oauth2 import service_account

        project_id = os.getenv("PROJECT_ID") if project_id is None else project_id
        if not project_id:
            raise ValueError("Please set your Google Cloud Project ID")
        self.close()
        if cred_file_path is None:
            connection = bigquery.Client(project=project_id, **kwargs)
        else:
            with open(cred_file_path, encoding="utf-8") as credential_file:
                credentials = service_account.Credentials.from_service_account_info(
                    json.load(credential_file),
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
            connection = bigquery.Client(project=project_id, credentials=credentials, **kwargs)

        def run_sql(sql: str) -> pd.DataFrame:
            return connection.query(sql).result().to_dataframe()

        self._close_connection = connection.close
        self._run_sql = run_sql
        self.dialect = "BigQuery SQL"

    @_serialized
    def connect_to_duckdb(self, url: str, init_sql: str | None = None, **kwargs: Any) -> None:
        import duckdb

        if url in (":memory:", ""):
            path = ":memory:"
        elif os.path.exists(url) or url.startswith(("md:", "motherduck:")):
            path = url
        else:
            path = os.path.basename(urlparse(url).path)
            if not path:
                raise ValueError("Database URL must include a file name")
            if not os.path.exists(path):
                with requests.get(url, timeout=(10, 60)) as response:
                    response.raise_for_status()
                    with open(path, "wb") as database_file:
                        database_file.write(response.content)
        self.close()
        connection = duckdb.connect(path, **kwargs)
        try:
            if init_sql is not None:
                connection.query(init_sql)
        except BaseException:
            connection.close()
            raise

        def run_sql(sql: str) -> pd.DataFrame:
            # The instance lock covers query execution and full result consumption,
            # preserving init_sql's temporary tables and connection settings.
            return connection.query(sql).to_df()

        self._close_connection = connection.close
        self._run_sql = run_sql
        self.dialect = "DuckDB SQL"

    @_serialized
    def connect_to_mssql(self, odbc_conn_str: str, **kwargs: Any) -> None:
        connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": odbc_conn_str})
        self.close()
        engine = create_engine(connection_url, **kwargs)

        def run_sql(sql: str) -> pd.DataFrame:
            with engine.begin() as connection:
                return pd.read_sql_query(text(sql), connection)

        self._close_connection = engine.dispose
        self._run_sql = run_sql
        self.dialect = "T-SQL / Microsoft SQL Server"

    @_serialized
    def connect_to_presto(
        self, host: str, catalog: str = "hive", schema: str = "default",
        user: str | None = None, password: str | None = None,
        port: int | None = None, combined_pem_path: str | None = None,
        protocol: str = "https", requests_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        from pyhive import presto

        host = os.getenv("PRESTO_HOST") if host is None else host
        catalog = os.getenv("PRESTO_CATALOG") if catalog is None else catalog
        user = os.getenv("PRESTO_USER") if user is None else user
        password = os.getenv("PRESTO_PASSWORD") if password is None else password
        configured_port = os.getenv("PRESTO_PORT") if port is None else port
        if not host or not catalog or not user or configured_port is None:
            raise ValueError("Please set your presto host, catalog, user and port")
        if requests_kwargs is None and combined_pem_path is not None:
            requests_kwargs = {"verify": combined_pem_path}
        self.close()
        connection = presto.Connection(
            host=host, username=user, password=password, catalog=catalog, schema=schema,
            port=int(configured_port), protocol=protocol, requests_kwargs=requests_kwargs, **kwargs,
        )

        def run_sql(sql: str) -> pd.DataFrame:
            return self._query_frame(connection, sql.rstrip().removesuffix(";"))

        self._close_connection = connection.close
        self._run_sql = run_sql
        self.dialect = "Presto"

    @_serialized
    def connect_to_hive(
        self, host: str | None = None, dbname: str = "default", user: str | None = None,
        password: str | None = None, port: int | None = None, auth: str = "CUSTOM", **kwargs: Any,
    ) -> None:
        from pyhive import hive

        host = os.getenv("HIVE_HOST") if host is None else host
        dbname = os.getenv("HIVE_DATABASE") if dbname is None else dbname
        user = os.getenv("HIVE_USER") if user is None else user
        password = os.getenv("HIVE_PASSWORD") if password is None else password
        configured_port = os.getenv("HIVE_PORT") if port is None else port
        if not host or not dbname or not user or configured_port is None:
            raise ValueError("Please set your hive host, database, user and port")
        self.close()
        connection = hive.Connection(
            host=host, username=user, password=password, database=dbname,
            port=int(configured_port), auth=auth, **kwargs,
        )

        def run_sql(sql: str) -> pd.DataFrame:
            return self._query_frame(connection, sql)

        self._close_connection = connection.close
        self._run_sql = run_sql
        self.dialect = "Hive"

    @_serialized
    def run_sql(self, sql: str) -> pd.DataFrame:
        if self._run_sql is None:
            raise RuntimeError("You need to connect to a database before running SQL")
        return self._run_sql(sql)
