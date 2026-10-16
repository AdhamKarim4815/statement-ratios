"""Year-over-year growth rates and compound annual growth rates (CAGR)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from .models import FiscalYear
from .ratios import free_cash_flow, gross_profit

METRICS: tuple[tuple[str, str, Callable[[FiscalYear], float]], ...] = (
    ("revenue", "Revenue", lambda fy: fy.income["revenue"]),
    ("gross_profit", "Gross profit", gross_profit),
    ("operating_income", "Operating income", lambda fy: fy.income["operating_income"]),
    ("net_income", "Net income", lambda fy: fy.income["net_income"]),
    ("operating_cash_flow", "Operating cash flow", lambda fy: fy.cash_flow["operating_cash_flow"]),
    ("free_cash_flow", "Free cash flow", free_cash_flow),
    ("total_assets", "Total assets", lambda fy: fy.balance["total_assets"]),
    ("total_equity", "Total equity", lambda fy: fy.balance["total_equity"]),
)


def growth_rate(previous: float, current: float) -> float | None:
    """(current - previous) / |previous|; None when previous is zero."""
    if previous == 0:
        return None
    return (current - previous) / abs(previous)


def cagr(start: float, end: float, periods: int) -> float | None:
    """Compound annual growth rate; None unless both ends are positive and periods >= 1."""
    if periods < 1 or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1.0 / periods) - 1.0


@dataclass(frozen=True)
class Trend:
    key: str
    label: str
    values: dict[int, float]
    yoy: dict[int, float | None]  # keyed by the later year of each pair
    cagr: float | None
    periods: int


def compute_trends(years: Sequence[FiscalYear]) -> list[Trend]:
    """Growth for each headline metric across ``years`` (ascending). Needs two or more years."""
    if len(years) < 2:
        return []
    trends: list[Trend] = []
    for key, label, getter in METRICS:
        values = {fy.year: getter(fy) for fy in years}
        yoy = {cur.year: growth_rate(getter(prev), getter(cur)) for prev, cur in pairwise(years)}
        periods = len(years) - 1
        trends.append(
            Trend(
                key,
                label,
                values,
                yoy,
                cagr(values[years[0].year], values[years[-1].year], periods),
                periods,
            )
        )
    return trends
