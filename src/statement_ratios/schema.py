"""The expected input schema, a runnable template and a human-readable description."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import BALANCE, CASH_FLOW, INCOME, STATEMENTS


@dataclass(frozen=True)
class FieldSpec:
    name: str
    required: bool
    description: str
    signed: bool = False  # True if a negative value is legitimate


SCHEMA: dict[str, tuple[FieldSpec, ...]] = {
    INCOME: (
        FieldSpec("revenue", True, "Total net sales / revenue"),
        FieldSpec("cost_of_goods_sold", True, "Direct cost of revenue (COGS, cost of sales)"),
        FieldSpec("operating_income", True, "Operating income, used as EBIT", signed=True),
        FieldSpec("interest_expense", True, "Interest expense, entered as a positive number"),
        FieldSpec("income_before_tax", True, "Pre-tax income (EBT)", signed=True),
        FieldSpec("income_tax_expense", True, "Income tax expense (negative = benefit)", True),
        FieldSpec("net_income", True, "Net income after tax", signed=True),
    ),
    BALANCE: (
        FieldSpec("cash", True, "Cash and cash equivalents"),
        FieldSpec("short_term_investments", False, "Marketable securities (default 0)"),
        FieldSpec("receivables", True, "Accounts receivable, net"),
        FieldSpec("inventory", True, "Inventories (0 for service or software firms)"),
        FieldSpec("current_assets", True, "Total current assets"),
        FieldSpec("total_assets", True, "Total assets"),
        FieldSpec("accounts_payable", True, "Accounts payable"),
        FieldSpec("current_liabilities", True, "Total current liabilities"),
        FieldSpec("short_term_debt", True, "Short-term debt and current portion of long-term debt"),
        FieldSpec("long_term_debt", True, "Long-term debt, excluding the current portion"),
        FieldSpec("total_liabilities", True, "Total liabilities"),
        FieldSpec("total_equity", True, "Total shareholders' equity", signed=True),
        FieldSpec("retained_earnings", True, "Retained earnings", signed=True),
        FieldSpec("market_value_equity", False, "Market capitalisation (Altman X4; else book)"),
        FieldSpec("shares_outstanding", False, "Shares outstanding (Piotroski dilution test)"),
    ),
    CASH_FLOW: (
        FieldSpec("operating_cash_flow", True, "Net cash from operating activities", signed=True),
        FieldSpec("capital_expenditures", True, "Capital expenditures, entered as positive"),
        FieldSpec("depreciation_amortization", True, "Depreciation and amortisation"),
    ),
}

TOP_LEVEL_KEYS = ("company", "currency", "units", "synthetic", "note", "years")

# Template numbers, one tuple per statement, in the field order of SCHEMA above.
_TEMPLATE_VALUES: dict[int, tuple[tuple[float, ...], ...]] = {
    2023: (
        (900, 550, 130, 20, 110, 26, 84),
        (90, 0, 140, 190, 470, 950, 95, 290, 60, 260, 610, 340, 200, 700, 100),
        (120, 55, 48),
    ),
    2024: (
        (1000, 600, 150, 20, 130, 30, 100),
        (100, 0, 150, 200, 500, 1000, 100, 300, 50, 250, 600, 400, 250, 800, 100),
        (140, 60, 50),
    ),
}


def template() -> dict[str, Any]:
    """Return a small, valid, balanced two-year input document."""
    years: list[dict[str, Any]] = []
    for year, numbers in _TEMPLATE_VALUES.items():
        entry: dict[str, Any] = {"year": year}
        for stmt, values in zip(STATEMENTS, numbers, strict=True):
            names = [spec.name for spec in SCHEMA[stmt]]
            entry[stmt] = dict(zip(names, values, strict=True))
        years.append(entry)
    return {
        "company": "Example Co.",
        "currency": "USD",
        "units": "millions",
        "synthetic": True,
        "note": "Template values are made up for illustration.",
        "years": years,
    }


def describe() -> str:
    """Return a plain-text reference for every accepted field."""
    lines = [
        "Input: a JSON object (or a wide CSV, see README) with these top-level keys:",
        "  company (required text), currency, units, synthetic (true/false), note, years",
        "",
        "Each entry of 'years' has 'year' (integer) plus three sections. Fiscal years",
        "must be consecutive. All amounts use one consistent unit.",
        "",
    ]
    for stmt in STATEMENTS:
        lines.append(f"{stmt}:")
        for spec in SCHEMA[stmt]:
            tag = "required" if spec.required else "optional"
            lines.append(f"  {spec.name:<26} {tag:<9} {spec.description}")
        lines.append("")
    lines.append("Template (run with --template to print only the JSON):")
    return "\n".join(lines)
