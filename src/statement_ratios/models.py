"""Core data model: errors, fiscal years and companies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

INCOME = "income_statement"
BALANCE = "balance_sheet"
CASH_FLOW = "cash_flow"
STATEMENTS = (INCOME, BALANCE, CASH_FLOW)


class InputError(ValueError):
    """Raised for any problem with user input (file, schema or year selection)."""


class ValidationError(InputError):
    """Raised when the input file parses but its contents are invalid.

    All problems found are collected in ``errors`` so users can fix them in one pass.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class FiscalYear:
    """The three statements for one fiscal year (values in a consistent unit)."""

    year: int
    income: Mapping[str, float]
    balance: Mapping[str, float]
    cash_flow: Mapping[str, float]


@dataclass(frozen=True)
class Company:
    """A company with one or more fiscal years, sorted ascending by year."""

    name: str
    years: tuple[FiscalYear, ...]
    currency: str = "USD"
    units: str = ""
    synthetic: bool = False
    note: str = ""

    @property
    def year_numbers(self) -> list[int]:
        return [fy.year for fy in self.years]

    def get(self, year: int) -> FiscalYear:
        for fy in self.years:
            if fy.year == year:
                return fy
        available = ", ".join(str(y) for y in self.year_numbers)
        raise InputError(f"year {year} not found in input (available: {available})")

    def previous(self, year: int) -> FiscalYear | None:
        """Return the fiscal year immediately before ``year``, if present."""
        prior = [fy for fy in self.years if fy.year == year - 1]
        return prior[0] if prior else None
