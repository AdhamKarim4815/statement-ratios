"""Single-year ratio calculations.

Every ratio uses year-end balances (no averaging), so each result can be checked by hand
from one set of statements. A ratio whose denominator is zero (or not meaningful, such as
a negative equity base) is returned as ``None`` and shown as "n/a" in reports.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .models import FiscalYear

DAYS_IN_YEAR = 365.0
Kind = Literal["x", "pct", "days", "money"]


@dataclass(frozen=True)
class Ratio:
    key: str
    label: str
    value: float | None
    kind: Kind
    formula: str = ""


def safe_div(num: float | None, den: float | None, *, positive: bool = False) -> float | None:
    """Divide, returning None for missing inputs or a zero denominator.

    With ``positive=True`` a negative denominator also yields None (used where the ratio
    is meaningless on a negative base, e.g. ROE on negative equity).
    """
    if num is None or den is None or den == 0 or (positive and den < 0):
        return None
    return num / den


# ---- building blocks shared with scores, flags and trends ----------------------------------


def total_debt(fy: FiscalYear) -> float:
    return fy.balance["short_term_debt"] + fy.balance["long_term_debt"]


def liquid_assets(fy: FiscalYear) -> float:
    """Cash plus short-term investments."""
    return fy.balance["cash"] + fy.balance.get("short_term_investments", 0.0)


def ebitda(fy: FiscalYear) -> float:
    return fy.income["operating_income"] + fy.cash_flow["depreciation_amortization"]


def gross_profit(fy: FiscalYear) -> float:
    return fy.income["revenue"] - fy.income["cost_of_goods_sold"]


def free_cash_flow(fy: FiscalYear) -> float:
    return fy.cash_flow["operating_cash_flow"] - fy.cash_flow["capital_expenditures"]


def effective_tax_rate(fy: FiscalYear) -> float:
    """Tax expense / pre-tax income, clamped to 0..1 (0 when pre-tax income is not positive)."""
    pretax = fy.income["income_before_tax"]
    if pretax <= 0:
        return 0.0
    return min(max(fy.income["income_tax_expense"] / pretax, 0.0), 1.0)


def nopat(fy: FiscalYear) -> float:
    return fy.income["operating_income"] * (1.0 - effective_tax_rate(fy))


def invested_capital(fy: FiscalYear) -> float:
    return total_debt(fy) + fy.balance["total_equity"] - liquid_assets(fy)


# ---- categories ----------------------------------------------------------------------------
# Each ratio: (key, label, value, kind, formula). Dense on purpose: one ratio per line pair.
# fmt: off


def liquidity(fy: FiscalYear) -> list[Ratio]:
    bs = fy.balance
    cl = bs["current_liabilities"]
    quick = liquid_assets(fy) + bs["receivables"]
    return [
        Ratio("current_ratio", "Current ratio", safe_div(bs["current_assets"], cl), "x",
              "current assets / current liabilities"),
        Ratio("quick_ratio", "Quick ratio", safe_div(quick, cl), "x",
              "(cash + short-term investments + receivables) / current liabilities"),
        Ratio("cash_ratio", "Cash ratio", safe_div(liquid_assets(fy), cl), "x",
              "(cash + short-term investments) / current liabilities"),
    ]


def leverage(fy: FiscalYear) -> list[Ratio]:
    equity, assets = fy.balance["total_equity"], fy.balance["total_assets"]
    debt = total_debt(fy)
    return [
        Ratio("debt_to_equity", "Debt / equity", safe_div(debt, equity, positive=True), "x",
              "(short-term debt + long-term debt) / total equity"),
        Ratio("debt_to_assets", "Debt / assets", safe_div(debt, assets), "x",
              "(short-term debt + long-term debt) / total assets"),
        Ratio("interest_coverage", "Interest coverage",
              safe_div(fy.income["operating_income"], fy.income["interest_expense"]), "x",
              "operating income (EBIT) / interest expense"),
        Ratio("net_debt_to_ebitda", "Net debt / EBITDA",
              safe_div(debt - liquid_assets(fy), ebitda(fy), positive=True), "x",
              "(total debt - cash - short-term investments) / (EBIT + D&A); n/a if EBITDA <= 0"),
    ]


def profitability(fy: FiscalYear) -> list[Ratio]:
    inc, bs = fy.income, fy.balance
    rev, ni = inc["revenue"], inc["net_income"]
    return [
        Ratio("gross_margin", "Gross margin", safe_div(gross_profit(fy), rev), "pct",
              "(revenue - COGS) / revenue"),
        Ratio("operating_margin", "Operating margin", safe_div(inc["operating_income"], rev),
              "pct", "operating income / revenue"),
        Ratio("net_margin", "Net margin", safe_div(ni, rev), "pct", "net income / revenue"),
        Ratio("roa", "Return on assets (ROA)", safe_div(ni, bs["total_assets"]), "pct",
              "net income / total assets"),
        Ratio("roe", "Return on equity (ROE)", safe_div(ni, bs["total_equity"], positive=True),
              "pct", "net income / total equity; n/a if equity <= 0"),
        Ratio("roic", "Return on invested capital (ROIC)",
              safe_div(nopat(fy), invested_capital(fy), positive=True), "pct",
              "NOPAT / (debt + equity - cash - short-term investments)"),
    ]


def efficiency(fy: FiscalYear) -> list[Ratio]:
    bs = fy.balance
    rev, cogs = fy.income["revenue"], fy.income["cost_of_goods_sold"]
    dso = safe_div(bs["receivables"] * DAYS_IN_YEAR, rev)
    dio = safe_div(bs["inventory"] * DAYS_IN_YEAR, cogs)
    dpo = safe_div(bs["accounts_payable"] * DAYS_IN_YEAR, cogs)
    ccc = None if dso is None or dio is None or dpo is None else dso + dio - dpo
    return [
        Ratio("asset_turnover", "Asset turnover", safe_div(rev, bs["total_assets"]), "x",
              "revenue / total assets"),
        Ratio("inventory_turnover", "Inventory turnover", safe_div(cogs, bs["inventory"]), "x",
              "COGS / inventory; n/a with no inventory"),
        Ratio("receivables_days", "Receivables days (DSO)", dso, "days",
              "receivables / revenue x 365"),
        Ratio("inventory_days", "Inventory days (DIO)", dio, "days", "inventory / COGS x 365"),
        Ratio("payables_days", "Payables days (DPO)", dpo, "days",
              "accounts payable / COGS x 365"),
        Ratio("cash_conversion_cycle", "Cash conversion cycle", ccc, "days", "DSO + DIO - DPO"),
    ]


def cash_flow_quality(fy: FiscalYear) -> list[Ratio]:
    ocf, fcf = fy.cash_flow["operating_cash_flow"], free_cash_flow(fy)
    return [
        Ratio("ocf_to_net_income", "Operating cash flow / net income",
              safe_div(ocf, fy.income["net_income"], positive=True), "x",
              "operating cash flow / net income; n/a if net income <= 0"),
        Ratio("free_cash_flow", "Free cash flow", fcf, "money",
              "operating cash flow - capital expenditures"),
        Ratio("fcf_margin", "FCF margin", safe_div(fcf, fy.income["revenue"]), "pct",
              "free cash flow / revenue"),
    ]


# fmt: on

CATEGORIES: tuple[tuple[str, Callable[[FiscalYear], list[Ratio]]], ...] = (
    ("Liquidity", liquidity),
    ("Leverage", leverage),
    ("Profitability", profitability),
    ("Efficiency", efficiency),
    ("Cash flow quality", cash_flow_quality),
)


def compute_ratios(fy: FiscalYear) -> dict[str, list[Ratio]]:
    """Return all ratios for one fiscal year, grouped by category in display order."""
    return {name: fn(fy) for name, fn in CATEGORIES}
