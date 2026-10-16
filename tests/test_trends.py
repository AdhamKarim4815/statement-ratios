"""Growth rates, CAGR and the multi-year trend table."""

from __future__ import annotations

import pytest

from conftest import make_year
from statement_ratios.trends import cagr, compute_trends, growth_rate


def test_growth_rate_basic():
    assert growth_rate(100, 110) == pytest.approx(0.10)
    assert growth_rate(100, 80) == pytest.approx(-0.20)


def test_growth_rate_zero_base_is_none():
    assert growth_rate(0, 50) is None


def test_growth_rate_from_a_loss_uses_absolute_base():
    assert growth_rate(-50, 100) == pytest.approx(3.0)


def test_cagr_two_years_of_ten_percent():
    assert cagr(1000, 1210, 2) == pytest.approx(0.10)


def test_cagr_single_period_equals_growth_rate():
    assert cagr(200, 250, 1) == pytest.approx(0.25)


@pytest.mark.parametrize(("start", "end"), [(0, 100), (-100, 100), (100, 0), (100, -5)])
def test_cagr_undefined_unless_both_ends_positive(start, end):
    assert cagr(start, end, 3) is None


def test_cagr_needs_at_least_one_period():
    assert cagr(100, 120, 0) is None


def test_compute_trends_revenue_series():
    years = [
        make_year(2022, income_statement={"revenue": 1000}),
        make_year(2023, income_statement={"revenue": 1100}),
        make_year(2024, income_statement={"revenue": 1210}),
    ]
    revenue = next(t for t in compute_trends(years) if t.key == "revenue")
    assert revenue.values == {2022: 1000, 2023: 1100, 2024: 1210}
    assert revenue.yoy[2023] == pytest.approx(0.10)
    assert revenue.yoy[2024] == pytest.approx(0.10)
    assert 2022 not in revenue.yoy
    assert revenue.cagr == pytest.approx(0.10)
    assert revenue.periods == 2


def test_compute_trends_needs_two_years():
    assert compute_trends([make_year(2024)]) == []


def test_free_cash_flow_trend_uses_ocf_minus_capex():
    years = [make_year(2023), make_year(2024, cash_flow={"operating_cash_flow": 160})]
    fcf = next(t for t in compute_trends(years) if t.key == "free_cash_flow")
    assert fcf.values == {2023: 75, 2024: 100}
    assert fcf.yoy[2024] == pytest.approx(1 / 3)
