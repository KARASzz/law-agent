import json
from pathlib import Path

from openpyxl import Workbook

from law_agent.client_profiles import ClientProfileStore
from law_agent.profile_pipeline import (
    ProfileCandidateStore,
    clean_assistant_workbook_to_candidates,
    clean_profile_workbook,
    load_pipeline_config,
    promote_candidates,
)


def _config(tmp_path: Path) -> dict:
    config = load_pipeline_config(None)
    config["candidate_db_path"] = str(tmp_path / "profile_candidates.db")
    config["client_profile_db_path"] = str(tmp_path / "client_profiles.db")
    config["output"]["pretty_json"] = True
    return config


def _save_profile_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "01_极简采集表"
    ws.append(
        [
            "采集ID",
            "采集日期",
            "数据来源",
            "案件类型",
            "阶段",
            "冲突结构",
            "角色格局",
            "客户核心诉求",
            "关键约束",
            "第一判断",
            "判断理由_抽象",
            "策略选择",
            "价值排序",
            "风险沟通方式",
            "处理温度",
            "结果/复盘",
            "可复用规则",
            "代表性",
            "备注_不写细节",
            "脱敏状态",
            "入库等级",
            "清洗备注",
            "复盘标签",
            "画像更新动作",
        ]
    )
    ws.append(
        [
            "100",
            "2026-05-05",
            "历史案件复盘",
            "民事合同",
            "咨询",
            "履行争议",
            "强弱明显",
            "止损",
            "证据不足",
            "可接",
            "法律关系不复杂但关键履行证据断裂。",
            "证据先行",
            "胜率优先",
            "直说高风险",
            "冷静理性",
            "未知",
            "遇到证据不足，倾向先补证。",
            "高",
            "测试",
            "已脱敏",
            "A核心画像",
            "测试",
            "判断准确",
            "强化旧规则",
        ]
    )
    wb.save(path)


def _save_assistant_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "每日协作记录"
    ws.append(
        [
            "日期",
            "助理姓名",
            "服务律师",
            "事项代号",
            "工作类型",
            "任务来源",
            "律师交代的任务",
            "我完成了什么",
            "交付物类型",
            "用时_分钟",
            "当前状态",
            "卡点原因",
            "律师反馈或修改方向",
            "下步跟进",
            "是否适合沉淀为习惯",
            "备注",
        ]
    )
    ws.append(
        [
            "2026-05-08",
            "小李",
            "张律师",
            "A客户合同争议",
            "案例检索",
            "微信/飞书文字交代",
            "查找类似违约责任案例",
            "整理5个相关案例并标注裁判要点",
            "法规/案例摘要",
            "90",
            "已交付，待律师确认",
            "无明显卡点",
            "以后优先列法院观点+可引用句",
            "等律师确认是否继续扩展检索",
            "是，律师有明确偏好",
            "",
        ]
    )
    ws.append(
        [
            "2026-05-08",
            "小李",
            "张律师",
            "B公司劳动争议",
            "时间节点整理",
            "客户材料触发",
            "梳理仲裁时效和证据提交节点",
            "按时间顺序整理关键节点",
            "时间轴",
            "88",
            "律师已确认",
            "材料不完整",
            "时间轴要单独标出风险日期",
            "等客户补劳动合同扫描件",
            "是，流程可以复用",
            "",
        ]
    )
    ws.append(
        [
            "2026-05-08",
            "小李",
            "张律师",
            "C客户沟通",
            "客户沟通辅助",
            "律师口头交代",
            "整理客户沟通要点",
            "形成沟通清单",
            "客户沟通要点",
            "30",
            "已交付",
            "无明显卡点",
            "不要直接联系 13812345678，应先发 test@example.com 给律师确认",
            "等律师确认",
            "是，话术可以复用",
            "",
        ]
    )
    ws.append(
        [
            "2026-05-08",
            "小李",
            "张律师",
            "D一次性事务",
            "行政事务",
            "助理主动发现",
            "整理文件",
            "完成归档",
            "归档文件",
            "20",
            "已归档",
            "无明显卡点",
            "无需沉淀",
            "",
            "否，只是一次性事务",
            "",
        ]
    )
    wb.save(path)


def test_clean_profile_workbook_output_can_be_ingested(tmp_path):
    input_path = tmp_path / "profile.xlsx"
    _save_profile_workbook(input_path)
    config = _config(tmp_path)

    output_path = clean_profile_workbook(input_path, tmp_path / "output", config)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["stats"]["records_exported"] == 1
    assert payload["records"][0]["quality_control"]["privacy_decision"] == "pass"

    store = ClientProfileStore(str(tmp_path / "profiles.db"))
    summary = store.ingest_json_file(str(output_path))
    assert summary.records_upserted == 1
    assert store.list_driver_profiles(matter_type="民事合同")[0]["strategy_choice"] == "证据先行"


def test_clean_assistant_workbook_writes_candidate_json_and_sqlite(tmp_path):
    input_path = tmp_path / "assistant.xlsx"
    _save_assistant_workbook(input_path)
    config = _config(tmp_path)

    output_path, summary = clean_assistant_workbook_to_candidates(
        input_path,
        tmp_path / "output",
        config,
        candidate_db_path=config["candidate_db_path"],
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["stats"]["candidates_exported"] == 3
    assert payload["stats"]["rows_skipped_not_suitable"] == 1
    assert payload["stats"]["candidates_need_manual_review"] == 1
    assert summary.candidates_upserted == 3

    store = ProfileCandidateStore(config["candidate_db_path"])
    candidates = store.list_candidates(limit=10)
    assert len(candidates) == 3
    assert any("常用交付物为【法规/案例摘要】" in item["candidate_rule"] for item in candidates)

    flagged = [item for item in candidates if item["quality_decision"] == "needs_manual_review"]
    assert len(flagged) == 1
    assert "手机号" in flagged[0]["sensitive_flags"]
    assert "邮箱" in flagged[0]["sensitive_flags"]


def test_promote_selected_candidates_imports_only_selected_pass_records(tmp_path):
    input_path = tmp_path / "assistant.xlsx"
    _save_assistant_workbook(input_path)
    config = _config(tmp_path)
    clean_assistant_workbook_to_candidates(
        input_path,
        tmp_path / "output",
        config,
        candidate_db_path=config["candidate_db_path"],
    )

    candidate_store = ProfileCandidateStore(config["candidate_db_path"])
    pass_candidates = candidate_store.list_candidates(
        quality_decision="pass",
        promotion_status="not_promoted",
        limit=10,
    )
    selected = pass_candidates[0]

    summary = promote_candidates(
        candidate_db_path=config["candidate_db_path"],
        client_profile_db_path=config["client_profile_db_path"],
        output_dir=tmp_path / "promoted",
        candidate_ids=[selected["candidate_id"]],
    )

    assert summary.records_seen == 1
    assert summary.records_promoted == 1

    promoted = candidate_store.get_candidate(selected["candidate_id"])
    assert promoted["promotion_status"] == "promoted"

    unpromoted = [
        item
        for item in candidate_store.list_candidates(limit=10)
        if item["candidate_id"] != selected["candidate_id"]
    ]
    assert any(item["promotion_status"] == "not_promoted" for item in unpromoted)

    profile_store = ClientProfileStore(config["client_profile_db_path"])
    profiles = profile_store.list_driver_profiles(matter_type="协作流程", limit=10)
    assert len(profiles) == 1
    assert profiles[0]["role_pattern"] == "律师-助理协作"
    assert profiles[0]["profile_update_action"] == "新增规则"


def test_workbench_has_no_batch_or_candidate_entry_points():
    html = Path("law_agent/static/workbench.html").read_text(encoding="utf-8")
    forbidden = [
        "候选画像池",
        "clean-assistant",
        "promote-candidates",
        "清洗助理",
        "批处理升格",
    ]
    for text in forbidden:
        assert text not in html
