from app.utils.line_item_utils import (
    deduplicate_non_operating_items,
    extract_original_name_from_standardized,
)


def test_extract_original_name_from_standardized():
    line_name = "Other Current Assets (Other current assets, net)"
    assert extract_original_name_from_standardized(line_name) == "Other current assets, net"
    assert extract_original_name_from_standardized("Other Current Assets") is None


def test_deduplicate_items_prefers_more_complete_entry():
    items = [
        {
            "line_name": "Cash and cash equivalents",
            "line_value": 100,
            "unit": None,
            "source": "balance_sheet",
        },
        {
            "line_name": "Cash & cash equivalents",
            "line_value": 100,
            "unit": "millions",
            "source": "balance_sheet",
        },
    ]

    deduped = deduplicate_non_operating_items(items)
    assert len(deduped) == 1
    assert deduped[0]["unit"] == "millions"
