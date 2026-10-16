"""Input validation and loading (JSON and CSV)."""

from __future__ import annotations

import copy
import json
import math

import pytest

from conftest import EXAMPLES, raw_document
from statement_ratios import InputError, ValidationError, build_company, load_company
from statement_ratios.loader import csv_to_raw, parse_json


def errors_for(raw, **kwargs) -> list[str]:
    with pytest.raises(ValidationError) as info:
        build_company(raw, **kwargs)
    return info.value.errors


def test_valid_document_builds_a_company():
    company = build_company(raw_document())
    assert company.name == "Test Co."
    assert company.year_numbers == [2023, 2024]
    assert company.get(2024).income["revenue"] == 1000
    assert company.previous(2024).year == 2023
    assert company.previous(2023) is None


def test_years_are_sorted_ascending():
    raw = raw_document()
    raw["years"].reverse()
    assert build_company(raw).year_numbers == [2023, 2024]


def test_missing_required_field_names_the_field():
    raw = raw_document()
    del raw["years"][1]["income_statement"]["revenue"]
    errors = errors_for(raw)
    assert any("FY2024" in e and "income_statement.revenue is missing" in e for e in errors)


def test_all_problems_are_reported_together():
    raw = raw_document()
    del raw["years"][0]["balance_sheet"]["cash"]
    del raw["years"][1]["cash_flow"]["operating_cash_flow"]
    assert len(errors_for(raw)) == 2


def test_missing_section_is_reported():
    raw = raw_document()
    del raw["years"][0]["cash_flow"]
    assert any("section 'cash_flow' is missing" in e for e in errors_for(raw))


def test_wrong_type_is_rejected():
    raw = raw_document()
    raw["years"][0]["income_statement"]["revenue"] = "1000"
    assert any("must be a finite number" in e for e in errors_for(raw))


def test_boolean_is_not_a_number():
    raw = raw_document()
    raw["years"][0]["income_statement"]["revenue"] = True
    assert any("must be a finite number" in e for e in errors_for(raw))


def test_non_finite_number_is_rejected():
    raw = raw_document()
    raw["years"][0]["income_statement"]["revenue"] = math.inf
    assert any("finite" in e for e in errors_for(raw))


def test_negative_value_rejected_where_not_allowed_but_ok_where_signed():
    raw = raw_document()
    raw["years"][0]["balance_sheet"]["inventory"] = -5
    assert any("inventory must not be negative" in e for e in errors_for(raw))
    ok = raw_document()
    ok["years"][0]["income_statement"]["net_income"] = -5
    ok["years"][0]["income_statement"]["operating_income"] = -5
    assert build_company(ok).get(2023).income["net_income"] == -5


def test_unknown_field_gets_a_suggestion():
    raw = raw_document()
    raw["years"][0]["balance_sheet"]["short_term_investment"] = 5
    assert any("did you mean 'short_term_investments'" in e for e in errors_for(raw))


def test_unknown_top_level_key_rejected():
    raw = raw_document()
    raw["compnay"] = "typo"
    assert any("did you mean 'company'" in e for e in errors_for(raw))


def test_balance_sheet_must_balance():
    raw = raw_document()
    raw["years"][1]["balance_sheet"]["total_equity"] = 450  # 600 + 450 != 1000
    errors = errors_for(raw)
    assert any("does not balance" in e and "FY2024" in e for e in errors)


def test_small_imbalance_within_tolerance_is_accepted():
    raw = raw_document()
    raw["years"][1]["balance_sheet"]["total_equity"] = 403  # off by 0.3% of assets
    assert build_company(raw).get(2024).balance["total_equity"] == 403


def test_tolerance_can_be_tightened():
    raw = raw_document()
    raw["years"][1]["balance_sheet"]["total_equity"] = 403
    assert any("does not balance" in e for e in errors_for(raw, tolerance=0.001))


def test_current_asset_components_cannot_exceed_current_assets():
    raw = raw_document()
    raw["years"][0]["balance_sheet"]["current_assets"] = 300
    assert any("exceeds current_assets" in e for e in errors_for(raw))


def test_duplicate_and_gapped_years_rejected():
    dup = raw_document((2024, 2024))
    assert any("duplicate" in e for e in errors_for(dup))
    gap = raw_document((2022, 2024))
    assert any("consecutive" in e for e in errors_for(gap))


def test_empty_years_and_wrong_top_level_rejected():
    assert any("non-empty list" in e for e in errors_for({"company": "X", "years": []}))
    assert any("top level" in e for e in errors_for([]))


def test_company_name_required():
    raw = raw_document()
    raw["company"] = " "
    assert any("'company'" in e for e in errors_for(raw))


def test_unknown_year_selection_lists_available_years():
    company = build_company(raw_document())
    with pytest.raises(InputError, match="available: 2023, 2024"):
        company.get(2030)


# ---- files ---------------------------------------------------------------------------------


def test_load_json_file(tmp_path):
    path = tmp_path / "co.json"
    path.write_text(json.dumps(raw_document()), encoding="utf-8")
    assert load_company(path).name == "Test Co."


def test_invalid_json_reports_location(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"company": ', encoding="utf-8")
    with pytest.raises(InputError, match="invalid JSON at line 1"):
        load_company(path)


def test_nan_in_json_is_rejected():
    with pytest.raises(InputError, match="NaN"):
        parse_json('{"a": NaN}')


def test_missing_file_and_bad_extension(tmp_path):
    with pytest.raises(InputError, match="file not found"):
        load_company(tmp_path / "nope.json")
    other = tmp_path / "data.txt"
    other.write_text("x")
    with pytest.raises(InputError, match="unsupported file type"):
        load_company(other)


def test_csv_matches_json_for_the_acme_example():
    from_json = load_company(EXAMPLES / "acme_industrial.json")
    from_csv = load_company(EXAMPLES / "acme_industrial.csv")
    assert from_csv == from_json


def test_csv_bad_header_rejected():
    with pytest.raises(InputError, match="header must start with"):
        csv_to_raw("item,value\nrevenue,5\n")


def test_csv_reports_non_numeric_cells_and_unknown_statements():
    text = "statement,item,2024\nincome_statement,revenue,abc\nprofit,x,1\n"
    with pytest.raises(ValidationError) as info:
        csv_to_raw(text)
    assert len(info.value.errors) == 2


def test_csv_company_name_defaults_to_file_stem(tmp_path):
    raw = csv_to_raw("statement,item,2024\nincome_statement,revenue,5\n", "my_file")
    assert raw["company"] == "my_file"


def test_raw_document_helper_is_not_mutated_between_tests():
    first = raw_document()
    snapshot = copy.deepcopy(first)
    build_company(first)
    assert first == snapshot
