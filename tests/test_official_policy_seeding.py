"""SQL seeds must supplement verified FAQ without duplicating existing rows."""

from types import SimpleNamespace

from scripts import seed_mysql_text2sql as subject


def test_existing_source_accepts_new_faq_and_hints_are_idempotent(monkeypatch):
    doc = {"doc_id": "official-1", "metadata": "{}"}
    hint = ("policy_documents", "doc_id", "description", "source identity")
    faq = {"doc_id": "official-1", "question": "新的官方问答"}
    saved_pairs = set()
    batches = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params=None):
            self.sql = sql

        def fetchall(self):
            if "FROM policy_documents" in self.sql:
                return [{"doc_id": "official-1"}]
            if "FROM policy_qa_pairs" in self.sql:
                return [{"doc_id": d, "question": q} for d, q in saved_pairs]
            if "FROM schema_hints" in self.sql:
                return [
                    dict(
                        zip(
                            ["table_name", "column_name", "hint_type", "hint_text"],
                            hint,
                        )
                    )
                ]
            raise AssertionError(self.sql)

    def insert(connection, sql, rows):
        batches.append((sql, list(rows)))
        if "INSERT INTO policy_qa_pairs" in sql:
            saved_pairs.update((row["doc_id"], row["question"]) for row in rows)

    monkeypatch.setattr(subject, "generate_documents", lambda count: [doc])
    monkeypatch.setattr(subject, "generate_entities", lambda docs: [])
    monkeypatch.setattr(subject, "generate_tags", lambda docs: [])
    monkeypatch.setattr(
        subject, "generate_qa_pairs", lambda docs: [faq] if docs else []
    )
    monkeypatch.setattr(subject, "generate_schema_hints", lambda: [hint])
    monkeypatch.setattr(subject, "bulk_insert", insert)
    connection = SimpleNamespace(cursor=Cursor)
    subject.seed_mysql(connection, 1)
    subject.seed_mysql(connection, 1)
    assert [rows for sql, rows in batches if "INSERT INTO policy_qa_pairs" in sql] == [
        [faq],
        [],
    ]
    assert all(not rows for sql, rows in batches if "INSERT INTO schema_hints" in sql)
