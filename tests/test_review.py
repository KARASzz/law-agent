"""
人工审阅任务测试
"""

from law_agent.review import ReviewTaskStore


def test_review_task_confirm_and_reject():
    store = ReviewTaskStore(":memory:")

    task = store.create_pending(
        trace_id="trace_1",
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
        intent="document_draft",
        risk_level="high",
        original_output="原始草稿",
    )

    assert task.review_status == "pending_review"
    assert task.original_output == "原始草稿"

    confirmed = store.confirm(
        trace_id="trace_1",
        reviewer_id="lawyer_1",
        reviewed_output="确认后草稿",
    )

    assert confirmed.review_status == "confirmed"
    assert confirmed.reviewer_id == "lawyer_1"
    assert confirmed.reviewed_output == "确认后草稿"
    assert confirmed.reviewed_at

    rejected = store.reject(
        trace_id="trace_1",
        reviewer_id="lawyer_2",
        rejection_reason="事实不足",
    )

    assert rejected.review_status == "rejected"
    assert rejected.reviewer_id == "lawyer_2"
    assert rejected.rejection_reason == "事实不足"


def test_review_task_list_filters():
    store = ReviewTaskStore(":memory:")

    store.create_pending(
        trace_id="trace_1",
        task_id="task_1",
        session_id="session_1",
        user_id="user_1",
        intent="document_draft",
        risk_level="high",
        original_output="高风险草稿",
    )
    store.create_pending(
        trace_id="trace_2",
        task_id="task_2",
        session_id="session_2",
        user_id="user_2",
        intent="case_search",
        risk_level="medium",
        original_output="中风险分析",
    )
    store.confirm("trace_2", reviewer_id="lawyer_1")

    pending = store.list_tasks(review_status="pending_review")
    confirmed = store.list_tasks(review_status="confirmed")
    high = store.list_tasks(risk_level="high")

    assert [task.trace_id for task in pending] == ["trace_1"]
    assert [task.trace_id for task in confirmed] == ["trace_2"]
    assert [task.trace_id for task in high] == ["trace_1"]
