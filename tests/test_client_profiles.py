"""
律师客户画像建库测试
"""

import json
from pathlib import Path

from law_agent.client_profiles import ClientProfileStore


def test_ingest_profile_json():
    payload = {
        "meta": {
            "schema_version": "lawyer_profile_memory_v1",
            "generated_at": "2026-05-05 16:47:32",
            "input_file": "律师客户画像.xlsx",
            "input_file_sha256": "abc",
        },
        "stats": {"records_exported": 1},
        "records": [
            {
                "record_id": "profile_1",
                "source": {
                    "source_file": "律师客户画像.xlsx",
                    "source_file_sha256": "abc",
                    "sheet_name": "01_极简采集表",
                    "excel_row_number": 7,
                },
                "taxonomy": {
                    "data_source": "历史案件复盘",
                    "matter_type": "民事合同",
                    "stage": "咨询",
                    "representativeness": "高",
                },
                "judgment_model": {
                    "conflict_structure": "履行争议",
                    "role_pattern": "强弱明显",
                    "client_goal": "止损",
                    "key_constraints": "证据不足",
                    "first_judgment": "可接",
                    "abstract_reason": "测试",
                    "strategy_choice": "证据先行",
                    "value_order": "胜率优先",
                    "risk_communication": "直说高风险",
                    "handling_temperature": "冷静理性",
                    "reusable_rule": "遇到X，倾向先Y。",
                },
                "review_and_ingestion": {
                    "collection_date": "2026-05-05",
                    "collection_id_or_masked_ref": "100",
                    "result_review": "未知",
                    "note": "测试",
                    "desensitization_status": "已脱敏",
                    "ingestion_level": "A核心画像",
                    "cleaning_note": "测试",
                    "review_tag": "判断准确",
                    "profile_update_action": "强化旧规则",
                },
                "quality_control": {
                    "missing_core_fields": [],
                    "privacy_decision": "pass",
                    "sensitive_flags": [],
                    "sensitive_flags_by_field": {},
                },
            }
        ],
    }
    workdir = Path("data/test_client_profiles")
    workdir.mkdir(parents=True, exist_ok=True)
    json_path = workdir / "profiles.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    db_path = workdir / "profiles.db"
    if db_path.exists():
        db_path.unlink()

    store = ClientProfileStore(str(db_path))
    summary = store.ingest_json_file(str(json_path))

    assert summary.records_seen == 1
    assert summary.records_upserted == 1

    record = store.get_record("profile_1")
    assert record["matter_type"] == "民事合同"
    assert record["strategy_choice"] == "证据先行"

    drivers = store.list_driver_profiles(matter_type="民事合同")
    assert len(drivers) == 1
    assert drivers[0]["profile_update_action"] == "强化旧规则"

    goal_drivers = store.list_driver_profiles(
        matter_type="民事合同",
        client_goal="止损",
    )
    assert len(goal_drivers) == 1
    assert goal_drivers[0]["record_id"] == "profile_1"

    missing_goal_drivers = store.list_driver_profiles(
        matter_type="民事合同",
        client_goal="回款",
    )
    assert missing_goal_drivers == []
