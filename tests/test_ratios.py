"""Single-year ratios checked against hand-computed values from the round-number base year."""

from __future__ import annotations

import pytest

from conftest import make_year
from statement_ratios.ratios import (
    compute_ratios,
    ebitda,
    effective_tax_rate,
    free_cash_flow,
    invested_capital,
    nopat,
    safe_div,
    total_debt,
)


def values(fy):
    return {r.key: r.value for group in compute_ratios(fy).values() for r in group}


def test_safe_div_handles_zero_none_and_negative_base():
    assert safe_div(10, 4) == 2.5
    assert safe_div(10, 0) is None
    assert safe_div(None, 5) is None
    assert safe_div(5, None) is None
    assert safe_div(5, -2) == -2.5
    assert safe_div(5, -2, positive=True) is None


def test_building_blocks():
    fy = make_year()
    assert total_debt(fy) == 300
    assert ebitda(fy) == 200
    assert free_cash_flow(fy) == 75
    assert effective_tax_rate(fy) == pytest.approx(0.25)
    assert nopat(fy) == pytest.approx(112.5)
    assert invested_capital(fy) == 550


def test_liquidity_ratios():
    v = values(make_year())
    assert v["current_ratio"] == pytest.approx(2.0)  # 500 / 250
    assert v["quick_ratio"] == pytest.approx(1.4)  # (100 + 50 + 200) / 250
    assert v["cash_ratio"] == pytest.approx(0.6)  # 150 / 250


def test_leverage_ratios():
    v = values(make_year())
    assert v["debt_to_equity"] == pytest.approx(0.75)  # 300 / 400
    assert v["debt_to_assets"] == pytest.approx(0.30)  # 300 / 1000
    assert v["interest_coverage"] == pytest.approx(5.0)  # 150 / 30
    assert v["net_debt_to_ebitda"] == pytest.approx(0.75)  # (300 - 150) / 200


def test_profitability_ratios():
    v = values(make_year())
    assert v["gross_margin"] == pytest.approx(0.40)
    assert v["operating_margin"] == pytest.approx(0.15)
    assert v["net_margin"] == pytest.approx(0.09)
    assert v["roa"] == pytest.approx(0.09)
    assert v["roe"] == pytest.approx(0.225)  # 90 / 400
    assert v["roic"] == pytest.approx(112.5 / 550)


def test_efficiency_ratios():
    v = values(make_year())
    assert v["asset_turnover"] == pytest.approx(1.0)
    assert v["inventory_turnover"] == pytest.approx(4.0)  # 600 / 150
    assert v["receivables_days"] == pytest.approx(73.0)  # 200 / 1000 * 365
    assert v["inventory_days"] == pytest.approx(91.25)  # 150 / 600 * 365
    assert v["payables_days"] == pytest.approx(100 / 600 * 365)
    assert v["cash_conversion_cycle"] == pytest.approx(73 + 91.25 - 100 / 600 * 365)


def test_cash_flow_quality_ratios():
    v = values(make_year())
    assert v["ocf_to_net_income"] == pytest.approx(1.5)  # 135 / 90
    assert v["free_cash_flow"] == pytest.approx(75)
    assert v["fcf_margin"] == pytest.approx(0.075)


def test_short_term_investments_default_to_zero():
    v = values(make_year(balance_sheet={"short_term_investments": None}))
    assert v["cash_ratio"] == pytest.approx(100 / 250)
    assert v["quick_ratio"] == pytest.approx(300 / 250)


def test_zero_inventory_gives_na_turnover_but_zero_days():
    v = values(make_year(balance_sheet={"inventory": 0, "current_assets": 350}))
    assert v["inventory_turnover"] is None
    assert v["inventory_days"] == 0
    assert v["cash_conversion_cycle"] == pytest.approx(73 - 100 / 600 * 365)


def test_zero_denominators_are_na_not_errors():
    fy = make_year(
        income_statement={"revenue": 0, "interest_expense": 0},
        balance_sheet={"current_liabilities": 0, "total_assets": 0},
    )
    v = values(fy)
    assert v["current_ratio"] is None
    assert v["interest_coverage"] is None
    assert v["gross_margin"] is None
    assert v["asset_turnover"] is None
    assert v["receivables_days"] is None
    assert v["cash_conversion_cycle"] is None


def test_negative_equity_makes_roe_and_debt_to_equity_na():
    v = values(make_year(balance_sheet={"total_equity": -100}))
    assert v["roe"] is None
    assert v["debt_to_equity"] is None


def test_nonpositive_ebitda_makes_net_debt_to_ebitda_na():
    v = values(make_year(income_statement={"operating_income": -80}))
    assert v["net_debt_to_ebitda"] is None


def test_ocf_to_net_income_na_on_loss():
    v = values(make_year(income_statement={"net_income": -10}))
    assert v["ocf_to_net_income"] is None


def test_tax_rate_is_zero_when_pretax_income_not_positive():
    fy = make_year(income_statement={"income_before_tax": -20, "income_tax_expense": 5})
    assert effective_tax_rate(fy) == 0.0
    assert nopat(fy) == 150


def test_tax_rate_is_clamped_to_unit_interval():
    fy = make_year(income_statement={"income_tax_expense": 500})
    assert effective_tax_rate(fy) == 1.0


def test_ratio_groups_are_in_display_order():
    groups = list(compute_ratios(make_year()))
    assert groups == ["Liquidity", "Leverage", "Profitability", "Efficiency", "Cash flow quality"]
