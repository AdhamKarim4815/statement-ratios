"""Altman Z-score and Piotroski F-score against worked examples and constructed cases."""

from __future__ import annotations

import pytest

from conftest import make_year
from statement_ratios.scores import altman, altman_zone, altman_zscore, piotroski

# ---- Altman --------------------------------------------------------------------------------


def test_altman_worked_example():
    # X1=0.20, X2=0.30, X3=0.10, X4=1.00, X5=1.50
    # Z = 1.2*0.2 + 1.4*0.3 + 3.3*0.1 + 0.6*1.0 + 1.0*1.5 = 0.24 + 0.42 + 0.33 + 0.60 + 1.50
    assert altman_zscore(0.20, 0.30, 0.10, 1.00, 1.50) == pytest.approx(3.09)


def test_altman_from_statements_matches_hand_calculation():
    # WC 250/1000, RE 300/1000, EBIT 150/1000, MVE 800 / liabilities 600, sales 1000/1000
    # Z = 1.2*0.25 + 1.4*0.30 + 3.3*0.15 + 0.6*(800/600) + 1.0*1.0 = 3.015
    result = altman(make_year())
    assert result.z == pytest.approx(3.015)
    assert result.zone == "safe"
    assert result.components["equity_to_liabilities"] == pytest.approx(800 / 600)
    assert not result.used_book_equity


def test_altman_falls_back_to_book_equity_without_market_value():
    result = altman(make_year(balance_sheet={"market_value_equity": None}))
    assert result.used_book_equity
    assert result.components["equity_to_liabilities"] == pytest.approx(400 / 600)
    # 0.30 + 0.42 + 0.495 + 0.6*(400/600) + 1.0
    assert result.z == pytest.approx(0.30 + 0.42 + 0.495 + 0.40 + 1.0)


@pytest.mark.parametrize(
    ("z", "zone"),
    [
        (3.5, "safe"),
        (2.99, "grey"),  # boundary belongs to the grey zone
        (2.5, "grey"),
        (1.81, "grey"),
        (1.80, "distress"),
        (0.2, "distress"),
        (-1.0, "distress"),
    ],
)
def test_altman_zone_boundaries(z, zone):
    assert altman_zone(z) == zone


def test_altman_distress_example():
    z = altman_zscore(-0.10, 0.0, -0.05, 0.30, 0.80)
    assert z == pytest.approx(-0.12 + 0.0 - 0.165 + 0.18 + 0.80)
    assert altman_zone(z) == "distress"


def test_altman_not_computable_without_liabilities():
    result = altman(make_year(balance_sheet={"total_liabilities": 0}))
    assert result.z is None
    assert result.zone is None
    assert "n/a" in result.interpretation


# ---- Piotroski -----------------------------------------------------------------------------


def good_pair():
    """Prior year weak, current year better on every one of the nine signals."""
    prior = make_year(
        2023,
        income_statement={"net_income": 10, "revenue": 800, "cost_of_goods_sold": 560},
        balance_sheet={
            "long_term_debt": 300,
            "current_assets": 400,
            "current_liabilities": 400,
            "shares_outstanding": 100,
        },
        cash_flow={"operating_cash_flow": 20},
    )
    current = make_year(
        2024,
        income_statement={"net_income": 50, "revenue": 1000, "cost_of_goods_sold": 600},
        balance_sheet={
            "long_term_debt": 200,
            "current_assets": 500,
            "current_liabilities": 250,
            "shares_outstanding": 100,
        },
        cash_flow={"operating_cash_flow": 80},
    )
    return current, prior


def test_piotroski_all_nine_pass():
    current, prior = good_pair()
    result = piotroski(current, prior)
    assert result.score == 9
    assert result.max_score == 9
    assert result.rating == "strong"
    assert all(c.passed for c in result.criteria)


def test_piotroski_all_nine_fail():
    current, prior = good_pair()
    result = piotroski(prior_as_bad(prior), current)
    assert result.score == 0
    assert result.rating == "weak"
    assert not any(c.passed for c in result.criteria)


def prior_as_bad(prior):
    """A year that is worse than good_pair's current year on every signal, with losses."""
    return make_year(
        2025,
        income_statement={"net_income": -20, "revenue": 700, "cost_of_goods_sold": 500},
        balance_sheet={
            "long_term_debt": 400,
            "current_assets": 300,
            "current_liabilities": 400,
            "shares_outstanding": 120,
        },
        cash_flow={"operating_cash_flow": -30},
    )


@pytest.mark.parametrize(
    ("criterion", "current_change"),
    [
        ("positive_roa", {"income_statement": {"net_income": -5}}),
        ("positive_cfo", {"cash_flow": {"operating_cash_flow": -1}}),
        ("roa_up", {"income_statement": {"net_income": 5}}),
        ("accruals", {"cash_flow": {"operating_cash_flow": 40}}),
        ("leverage_down", {"balance_sheet": {"long_term_debt": 350}}),
        ("current_ratio_up", {"balance_sheet": {"current_assets": 200}}),
        ("no_dilution", {"balance_sheet": {"shares_outstanding": 101}}),
        ("gross_margin_up", {"income_statement": {"cost_of_goods_sold": 800}}),
        ("asset_turnover_up", {"income_statement": {"revenue": 700, "cost_of_goods_sold": 420}}),
    ],
)
def test_piotroski_each_criterion_can_fail_alone(criterion, current_change):
    current, prior = good_pair()
    broken = make_year(
        2024,
        income_statement={**current.income, **current_change.get("income_statement", {})},
        balance_sheet={**current.balance, **current_change.get("balance_sheet", {})},
        cash_flow={**current.cash_flow, **current_change.get("cash_flow", {})},
    )
    result = piotroski(broken, prior)
    by_key = {c.key: c.passed for c in result.criteria}
    assert by_key[criterion] is False


def test_piotroski_equal_values_do_not_count_as_improvement():
    current, _ = good_pair()
    same = make_year(
        2023,
        income_statement=dict(current.income),
        balance_sheet=dict(current.balance),
        cash_flow=dict(current.cash_flow),
    )
    result = piotroski(current, same)
    by_key = {c.key: c.passed for c in result.criteria}
    assert by_key["roa_up"] is False
    assert by_key["current_ratio_up"] is False
    assert by_key["gross_margin_up"] is False
    assert by_key["asset_turnover_up"] is False
    assert by_key["no_dilution"] is True  # unchanged share count is not dilution


def test_piotroski_no_long_term_debt_passes_leverage_test():
    current, prior = good_pair()
    debt_free = make_year(
        2024,
        income_statement=dict(current.income),
        balance_sheet={**current.balance, "long_term_debt": 0},
        cash_flow=dict(current.cash_flow),
    )
    by_key = {c.key: c.passed for c in piotroski(debt_free, prior).criteria}
    assert by_key["leverage_down"] is True


def test_piotroski_missing_share_data_is_not_scored():
    current, prior = good_pair()
    no_shares = make_year(
        2024,
        income_statement=dict(current.income),
        balance_sheet={**current.balance, "shares_outstanding": None},
        cash_flow=dict(current.cash_flow),
    )
    result = piotroski(no_shares, prior)
    assert result.max_score == 8
    assert result.score == 8
    assert {c.key: c.passed for c in result.criteria}["no_dilution"] is None


def test_piotroski_rating_thresholds():
    current, prior = good_pair()
    assert piotroski(current, prior).rating == "strong"
    mixed = make_year(
        2024,
        income_statement=dict(current.income),
        balance_sheet={
            **current.balance,
            "shares_outstanding": 150,
            "current_assets": 200,
            "long_term_debt": 350,
        },
        cash_flow=dict(current.cash_flow),
    )
    result = piotroski(mixed, prior)
    assert result.score == 6
    assert result.rating == "moderate"
