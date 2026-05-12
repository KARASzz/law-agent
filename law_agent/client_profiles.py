"""
律师客户画像记忆库

负责把每周更新的脱敏画像 JSON 导入 SQLite，并把常用驱动字段展开成可检索列。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from law_agent.storage_sqlmodel import (
    CLIENT_PROFILE_SQLMODEL_MIGRATION_PLAN,
    SQLMODEL_AVAILABLE,
)


@dataclass
class IngestionSummary:
    """画像导入结果"""

    import_id: str
    source_file: str
    records_seen: int
    records_upserted: int
    records_skipped: int


class ClientProfileStore:
    """
    SQLite 版律师客户画像库。

    表设计：
    - profile_import_batches：每次 JSON 导入批次
    - lawyer_client_profiles：去标识化画像记录，一条 record_id 一条
    - profile_update_events：保留每周画像更新动作流水
    """

    def __init__(self, db_path: str = "data/client_profiles.db"):
        self.db_path = db_path
        self._init_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_import_batches (
                    import_id TEXT PRIMARY KEY,
                    schema_version TEXT,
                    generated_at TEXT,
                    input_file TEXT,
                    input_file_sha256 TEXT,
                    json_file_path TEXT NOT NULL,
                    json_file_sha256 TEXT NOT NULL,
                    stats_json TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lawyer_client_profiles (
                    record_id TEXT PRIMARY KEY,
                    latest_import_id TEXT NOT NULL,
                    source_file TEXT,
                    source_file_sha256 TEXT,
                    sheet_name TEXT,
                    excel_row_number INTEGER,
                    data_source TEXT,
                    matter_type TEXT,
                    stage TEXT,
                    representativeness TEXT,
                    conflict_structure TEXT,
                    role_pattern TEXT,
                    client_goal TEXT,
                    key_constraints TEXT,
                    first_judgment TEXT,
                    abstract_reason TEXT,
                    strategy_choice TEXT,
                    value_order TEXT,
                    risk_communication TEXT,
                    handling_temperature TEXT,
                    reusable_rule TEXT,
                    collection_date TEXT,
                    collection_ref TEXT,
                    result_review TEXT,
                    note TEXT,
                    desensitization_status TEXT,
                    ingestion_level TEXT,
                    cleaning_note TEXT,
                    review_tag TEXT,
                    profile_update_action TEXT,
                    missing_core_fields_json TEXT NOT NULL,
                    privacy_decision TEXT,
                    sensitive_flags_json TEXT NOT NULL,
                    sensitive_flags_by_field_json TEXT NOT NULL,
                    raw_record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(latest_import_id) REFERENCES profile_import_batches(import_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_update_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT NOT NULL,
                    import_id TEXT NOT NULL,
                    profile_update_action TEXT,
                    review_tag TEXT,
                    ingestion_level TEXT,
                    collection_date TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(record_id) REFERENCES lawyer_client_profiles(record_id),
                    FOREIGN KEY(import_id) REFERENCES profile_import_batches(import_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_profiles_matter_type ON lawyer_client_profiles(matter_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_profiles_stage ON lawyer_client_profiles(stage)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_profiles_client_goal ON lawyer_client_profiles(client_goal)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_profiles_first_judgment ON lawyer_client_profiles(first_judgment)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_profiles_ingestion_level ON lawyer_client_profiles(ingestion_level)"
            )

    def ingest_json_file(self, json_file_path: str) -> IngestionSummary:
        """导入模板 JSON 文件，按 record_id 幂等 upsert。"""
        path = Path(json_file_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = payload.get("meta", {})
        stats = payload.get("stats", {})
        records = payload.get("records", [])

        import_id = self._build_import_id(meta, path)
        imported_at = datetime.now().isoformat(timespec="seconds")
        json_sha256 = self._sha256_file(path)

        seen = 0
        upserted = 0
        skipped = 0

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO profile_import_batches (
                    import_id, schema_version, generated_at, input_file,
                    input_file_sha256, json_file_path, json_file_sha256,
                    stats_json, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    meta.get("schema_version"),
                    meta.get("generated_at"),
                    meta.get("input_file"),
                    meta.get("input_file_sha256"),
                    str(path),
                    json_sha256,
                    json.dumps(stats, ensure_ascii=False),
                    imported_at,
                ),
            )

            for record in records:
                seen += 1
                if self._should_skip(record):
                    skipped += 1
                    continue

                self._upsert_record(conn, record, import_id, imported_at)
                self._insert_update_event(conn, record, import_id, imported_at)
                upserted += 1

        return IngestionSummary(
            import_id=import_id,
            source_file=str(path),
            records_seen=seen,
            records_upserted=upserted,
            records_skipped=skipped,
        )

    def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """按 record_id 获取画像记录。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM lawyer_client_profiles WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_driver_profiles(
        self,
        matter_type: Optional[str] = None,
        stage: Optional[str] = None,
        client_goal: Optional[str] = None,
        first_judgment: Optional[str] = None,
        ingestion_level: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """列出可作为编排驱动的画像记录。"""
        conditions = ["privacy_decision = 'pass'"]
        params: List[Any] = []

        filters = {
            "matter_type": matter_type,
            "stage": stage,
            "client_goal": client_goal,
            "first_judgment": first_judgment,
            "ingestion_level": ingestion_level,
        }
        for column, value in filters.items():
            if value:
                conditions.append(f"{column} = ?")
                params.append(value)

        params.append(limit)
        sql = f"""
            SELECT * FROM lawyer_client_profiles
            WHERE {' AND '.join(conditions)}
            ORDER BY collection_date DESC, updated_at DESC
            LIMIT ?
        """

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_statistics(self) -> Dict[str, Any]:
        """获取画像库统计。"""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM lawyer_client_profiles").fetchone()[0]
            by_matter = dict(
                conn.execute(
                    """
                    SELECT COALESCE(matter_type, '未知'), COUNT(*)
                    FROM lawyer_client_profiles
                    GROUP BY matter_type
                    """
                ).fetchall()
            )
            by_action = dict(
                conn.execute(
                    """
                    SELECT COALESCE(profile_update_action, '未知'), COUNT(*)
                    FROM lawyer_client_profiles
                    GROUP BY profile_update_action
                    """
                ).fetchall()
            )

        return {
            "total_profiles": total,
            "matter_type_stats": by_matter,
            "profile_update_action_stats": by_action,
        }

    def get_sqlmodel_migration_plan(self) -> Dict[str, Any]:
        """返回客户画像库迁移到 SQLModel 的结构化计划。"""
        plan = dict(CLIENT_PROFILE_SQLMODEL_MIGRATION_PLAN)
        plan["sqlmodel_available"] = SQLMODEL_AVAILABLE
        plan["current_backend"] = "sqlite3"
        plan["target_backend"] = "sqlmodel"
        plan["db_path"] = self.db_path
        return plan

    def _upsert_record(
        self,
        conn: sqlite3.Connection,
        record: Dict[str, Any],
        import_id: str,
        now: str,
    ) -> None:
        source = record.get("source", {})
        taxonomy = record.get("taxonomy", {})
        judgment = record.get("judgment_model", {})
        review = record.get("review_and_ingestion", {})
        quality = record.get("quality_control", {})

        conn.execute(
            """
            INSERT INTO lawyer_client_profiles (
                record_id, latest_import_id, source_file, source_file_sha256,
                sheet_name, excel_row_number, data_source, matter_type, stage,
                representativeness, conflict_structure, role_pattern, client_goal,
                key_constraints, first_judgment, abstract_reason, strategy_choice,
                value_order, risk_communication, handling_temperature, reusable_rule,
                collection_date, collection_ref, result_review, note,
                desensitization_status, ingestion_level, cleaning_note, review_tag,
                profile_update_action, missing_core_fields_json, privacy_decision,
                sensitive_flags_json, sensitive_flags_by_field_json, raw_record_json,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(record_id) DO UPDATE SET
                latest_import_id = excluded.latest_import_id,
                source_file = excluded.source_file,
                source_file_sha256 = excluded.source_file_sha256,
                sheet_name = excluded.sheet_name,
                excel_row_number = excluded.excel_row_number,
                data_source = excluded.data_source,
                matter_type = excluded.matter_type,
                stage = excluded.stage,
                representativeness = excluded.representativeness,
                conflict_structure = excluded.conflict_structure,
                role_pattern = excluded.role_pattern,
                client_goal = excluded.client_goal,
                key_constraints = excluded.key_constraints,
                first_judgment = excluded.first_judgment,
                abstract_reason = excluded.abstract_reason,
                strategy_choice = excluded.strategy_choice,
                value_order = excluded.value_order,
                risk_communication = excluded.risk_communication,
                handling_temperature = excluded.handling_temperature,
                reusable_rule = excluded.reusable_rule,
                collection_date = excluded.collection_date,
                collection_ref = excluded.collection_ref,
                result_review = excluded.result_review,
                note = excluded.note,
                desensitization_status = excluded.desensitization_status,
                ingestion_level = excluded.ingestion_level,
                cleaning_note = excluded.cleaning_note,
                review_tag = excluded.review_tag,
                profile_update_action = excluded.profile_update_action,
                missing_core_fields_json = excluded.missing_core_fields_json,
                privacy_decision = excluded.privacy_decision,
                sensitive_flags_json = excluded.sensitive_flags_json,
                sensitive_flags_by_field_json = excluded.sensitive_flags_by_field_json,
                raw_record_json = excluded.raw_record_json,
                updated_at = excluded.updated_at
            """,
            (
                record["record_id"],
                import_id,
                source.get("source_file"),
                source.get("source_file_sha256"),
                source.get("sheet_name"),
                source.get("excel_row_number"),
                taxonomy.get("data_source"),
                taxonomy.get("matter_type"),
                taxonomy.get("stage"),
                taxonomy.get("representativeness"),
                judgment.get("conflict_structure"),
                judgment.get("role_pattern"),
                judgment.get("client_goal"),
                judgment.get("key_constraints"),
                judgment.get("first_judgment"),
                judgment.get("abstract_reason"),
                judgment.get("strategy_choice"),
                judgment.get("value_order"),
                judgment.get("risk_communication"),
                judgment.get("handling_temperature"),
                judgment.get("reusable_rule"),
                review.get("collection_date"),
                review.get("collection_id_or_masked_ref"),
                review.get("result_review"),
                review.get("note"),
                review.get("desensitization_status"),
                review.get("ingestion_level"),
                review.get("cleaning_note"),
                review.get("review_tag"),
                review.get("profile_update_action"),
                json.dumps(quality.get("missing_core_fields", []), ensure_ascii=False),
                quality.get("privacy_decision"),
                json.dumps(quality.get("sensitive_flags", []), ensure_ascii=False),
                json.dumps(quality.get("sensitive_flags_by_field", {}), ensure_ascii=False),
                json.dumps(record, ensure_ascii=False),
                now,
                now,
            ),
        )

    def _insert_update_event(
        self,
        conn: sqlite3.Connection,
        record: Dict[str, Any],
        import_id: str,
        now: str,
    ) -> None:
        review = record.get("review_and_ingestion", {})
        conn.execute(
            """
            INSERT INTO profile_update_events (
                record_id, import_id, profile_update_action, review_tag,
                ingestion_level, collection_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["record_id"],
                import_id,
                review.get("profile_update_action"),
                review.get("review_tag"),
                review.get("ingestion_level"),
                review.get("collection_date"),
                now,
            ),
        )

    def _should_skip(self, record: Dict[str, Any]) -> bool:
        if not record.get("record_id"):
            return True
        quality = record.get("quality_control", {})
        return quality.get("privacy_decision") != "pass"

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        json_fields = [
            "missing_core_fields_json",
            "sensitive_flags_json",
            "sensitive_flags_by_field_json",
            "raw_record_json",
        ]
        for field in json_fields:
            if field in data:
                data[field.replace("_json", "")] = json.loads(data[field])
                del data[field]
        return data

    def _build_import_id(self, meta: Dict[str, Any], path: Path) -> str:
        raw = "|".join(
            [
                meta.get("schema_version", ""),
                meta.get("generated_at", ""),
                meta.get("input_file_sha256", ""),
                str(path),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def _sha256_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


def import_profile_json(json_file_path: str, db_path: str = "data/client_profiles.db") -> IngestionSummary:
    """便捷函数：导入客户画像 JSON。"""
    store = ClientProfileStore(db_path)
    return store.ingest_json_file(json_file_path)


def main(argv: Optional[Iterable[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="律师客户画像建库工具")
    parser.add_argument("json_file", help="画像 JSON 文件路径")
    parser.add_argument("--db", default="data/client_profiles.db", help="SQLite 数据库路径")
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary = import_profile_json(args.json_file, args.db)
    print(
        json.dumps(
            {
                "import_id": summary.import_id,
                "source_file": summary.source_file,
                "records_seen": summary.records_seen,
                "records_upserted": summary.records_upserted,
                "records_skipped": summary.records_skipped,
                "db_path": args.db,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
