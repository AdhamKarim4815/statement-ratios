"""Shared fixtures: a base fiscal year of round numbers, so results can be checked by hand."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from statement_ratios import Company, FiscalYear

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

# Round-number base year. Hand-computed expectations in the tests refer to these values:
#   gross profit 400, EBITDA 200, total debt 300, liquid assets 150 (cash 100 + investments 50),
#   equity 400, assets 1000, liabilities 600 (250 current), net income 90 = 120 pre-tax * 75%.
BASE: dict[str, dict[str, float]] = {
    "income_statement": {
        "revenue": 1000,
        "cost_of_goods_sold": 600,
        "operating_income": 150,
        "interest_expense": 30,
        "income_before_tax": 120,
        "income_tax_expense": 30,
        "net_income": 90,
    },
    "balance_sheet": {
        "cash": 100,
        "short_term_investments": 50,
        "receivables": 200,
        "inventory": 150,
        "current_assets": 500,
        "total_assets": 1000,
        "accounts_payable": 100,
        "current_liabilities": 250,
        "short_term_debt": 50,
        "long_term_debt": 250,
        "total_liabilities": 600,
        "total_equity": 400,
        "retained_earnings": 300,
        "market_value_equity": 800,
        "shares_outstanding": 100,
    },
    "cash_flow": {
        "operating_cash_flow": 135,
        "capital_expenditures": 60,
        "depreciation_amortization": 50,
    },
}


def make_year(year: int = 2024, **overrides: dict[str, float]) -> FiscalYear:
    """Build a FiscalYear from BASE; pass income_statement={...} etc. to override items.

    A value of None removes the item (useful for optional fields).
    """
    data: dict[str, Any] = copy.deepcopy(BASE)
    for stmt, changes in overrides.items():
        for key, value in changes.items():
            if value is None:
                data[stmt].pop(key, None)
            else:
                data[stmt][key] = value
    return FiscalYear(year, data["income_statement"], data["balance_sheet"], data["cash_flow"])


def raw_document(years: tuple[int, ...] = (2023, 2024)) -> dict[str, Any]:
    """A valid raw (JSON-shaped) document built from BASE."""
    return {
        "company": "Test Co.",
        "years": [{"year": y, **copy.deepcopy(BASE)} for y in years],
    }


@pytest.fixture
def year():
    return make_year


@pytest.fixture
def company() -> Company:
    return Company("Test Co.", (make_year(2023), make_year(2024)))
