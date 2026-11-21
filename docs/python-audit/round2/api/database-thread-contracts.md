# DBAccess 的线程与关闭边界

2026-11-15。审核包含八个适配器，未连接外部数据库，也未安装缺少的可选驱动。

`DBAccess` 的 connect、run_sql 和 close 使用同一 `RLock`；一个查询的执行、完整取数、游标关闭和失败回滚都在锁内。重连内部调用 close，因此使用可重入锁。借用实例由调用方关闭；取消等待线程查询不会声称数据库工作已停止。

| 适配器 | 核对的实际边界 |
| --- | --- |
| MySQL / PyMySQL | 官方实现声明 threadsafety=1，纯 Python 连接持有 socket/结果状态；本地已安装源码无创建线程身份检查。统一锁保护完整事务/游标范围，不能无锁共享。 |
| PostgreSQL / psycopg2 | 官方文档明确连接可跨普通线程共享，游标单次拥有；本实现完整串行查询并关闭游标。 |
| Oracle / oracledb | 官方 threadsafety=2，连接可共享，游标不可共享；本实现单次创建并关闭游标。 |
| BigQuery | 官方 DB-API 声明 threadsafety=2；客户端查询和完整结果获取串行，close 同一锁。未把 bigqueryconnection 的 gRPC 文档误作 bigquery 客户端证据。 |
| DuckDB | 当前官方文档跳转到 2.0 LTS，明确同一连接忙时其它线程调用会失败，并说明 cursor 拥有独立事务与会话设置。保留原 connection.query，并在统一锁内完整 to_df，保留 init_sql/TEMP 表与会话语义。此处推断是：禁止重叠调用不等于创建线程亲和。未对未安装版本宣称真实集成验证。 |
| MSSQL / SQLAlchemy | 保存的是可共享 Engine；每次查询在执行线程的 engine.begin 中取得/释放连接，未共享借出的 Connection。 |
| Presto / PyHive | 官方源码 threadsafety=2；Connection 是游标工厂，每次查询独立游标。 |
| Hive / PyHive | 官方源码 threadsafety=2；新游标仅在查询拥有线程使用和关闭。 |

离线行为回归证明查询与 close 不重叠、DuckDB 查询保留同一初始化连接；它们不证明八种服务器/驱动的完整集成行为。

来源：

- [PEP 249 threadsafety 与 mutex 的适用边界](https://peps.python.org/pep-0249/#threadsafety)
- [PyMySQL 官方源码](https://github.com/PyMySQL/PyMySQL/blob/main/pymysql/__init__.py)
- [psycopg2 线程与进程安全](https://www.psycopg.org/docs/usage.html#thread-and-process-safety)
- [oracledb threadsafety](https://python-oracledb.readthedocs.io/en/latest/api_manual/module.html#oracledb.threadsafety)
- [BigQuery DB-API 官方源码](https://github.com/googleapis/python-bigquery/blob/main/google/cloud/bigquery/dbapi/__init__.py)
- [DuckDB 2.0 Python DB API](https://duckdb.org/docs/2.0/clients/python/dbapi)
- [SQLAlchemy Engine 与连接范围](https://docs.sqlalchemy.org/en/20/core/connections.html)
- [PyHive Presto 官方源码](https://github.com/dropbox/PyHive/blob/master/pyhive/presto.py)
- [PyHive Hive 官方源码](https://github.com/dropbox/PyHive/blob/master/pyhive/hive.py)
