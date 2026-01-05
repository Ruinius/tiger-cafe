import uuid

from app.utils.financial_statement_progress import (
    FinancialStatementMilestone,
    MilestoneStatus,
    add_log,
    clear_progress,
    get_progress,
    initialize_progress,
    reset_balance_sheet_milestones,
    reset_income_statement_milestones,
    update_milestone,
)


def test_initialize_and_update_milestone_tracks_logs():
    document_id = str(uuid.uuid4())
    try:
        initialize_progress(document_id)

        update_milestone(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            MilestoneStatus.IN_PROGRESS,
            message="Started extraction",
        )

        progress = get_progress(document_id)
        milestone = progress["milestones"][
            FinancialStatementMilestone.BALANCE_SHEET.value
        ]

        assert milestone["status"] == MilestoneStatus.IN_PROGRESS.value
        assert milestone["message"] == "Started extraction"
        assert milestone["logs"][0]["message"] == "Started extraction"
        assert progress["last_updated"]
    finally:
        clear_progress(document_id)


def test_add_log_truncates_to_last_20_and_preserves_status():
    document_id = str(uuid.uuid4())
    try:
        initialize_progress(document_id)
        update_milestone(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            MilestoneStatus.IN_PROGRESS,
            message="Initial",
        )

        for index in range(25):
            add_log(
                document_id,
                FinancialStatementMilestone.INCOME_STATEMENT,
                f"log-{index}",
            )

        progress = get_progress(document_id)
        milestone = progress["milestones"][
            FinancialStatementMilestone.INCOME_STATEMENT.value
        ]

        assert milestone["status"] == MilestoneStatus.IN_PROGRESS.value
        assert len(milestone["logs"]) == 20
        assert milestone["logs"][0]["message"] == "log-5"
        assert milestone["logs"][-1]["message"] == "log-24"
    finally:
        clear_progress(document_id)


def test_reset_balance_and_income_milestones():
    document_id = str(uuid.uuid4())
    try:
        initialize_progress(document_id)
        update_milestone(
            document_id,
            FinancialStatementMilestone.BALANCE_SHEET,
            MilestoneStatus.COMPLETED,
            message="Done",
        )
        update_milestone(
            document_id,
            FinancialStatementMilestone.INCOME_STATEMENT,
            MilestoneStatus.ERROR,
            message="Failed",
        )
        update_milestone(
            document_id,
            FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS,
            MilestoneStatus.COMPLETED,
            message="Done",
        )

        reset_balance_sheet_milestones(document_id)
        progress = get_progress(document_id)

        balance_milestone = progress["milestones"][
            FinancialStatementMilestone.BALANCE_SHEET.value
        ]
        income_milestone = progress["milestones"][
            FinancialStatementMilestone.INCOME_STATEMENT.value
        ]
        additional_milestone = progress["milestones"][
            FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS.value
        ]

        assert balance_milestone["status"] == MilestoneStatus.PENDING.value
        assert income_milestone["status"] == MilestoneStatus.ERROR.value
        assert additional_milestone["status"] == MilestoneStatus.COMPLETED.value

        reset_income_statement_milestones(document_id)
        progress = get_progress(document_id)
        income_milestone = progress["milestones"][
            FinancialStatementMilestone.INCOME_STATEMENT.value
        ]
        additional_milestone = progress["milestones"][
            FinancialStatementMilestone.EXTRACTING_ADDITIONAL_ITEMS.value
        ]
        non_operating_milestone = progress["milestones"][
            FinancialStatementMilestone.CLASSIFYING_NON_OPERATING_ITEMS.value
        ]

        assert income_milestone["status"] == MilestoneStatus.PENDING.value
        assert additional_milestone["status"] == MilestoneStatus.PENDING.value
        assert non_operating_milestone["status"] == MilestoneStatus.PENDING.value
    finally:
        clear_progress(document_id)
