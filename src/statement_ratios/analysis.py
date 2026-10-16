"""Orchestration: run every calculation for a company."""

from __future__ import annotations

from dataclasses import dataclass

from .dupont import DuPont, dupont
from .flags import Flag, generate_flags
from .models import Company
from .ratios import Ratio, compute_ratios
from .scores import AltmanResult, PiotroskiResult, altman, piotroski
from .trends import Trend, compute_trends


@dataclass(frozen=True)
class YearResult:
    year: int
    ratios: dict[str, list[Ratio]]
    dupont: DuPont
    altman: AltmanResult
    piotroski: PiotroskiResult | None  # None for the first year (needs a prior year)
    flags: list[Flag]

    def values(self) -> dict[str, float | None]:
        """Flat mapping of ratio key to value."""
        return {r.key: r.value for group in self.ratios.values() for r in group}


@dataclass(frozen=True)
class Analysis:
    company: Company
    results: list[YearResult]
    trends: list[Trend]


def analyze(company: Company, year: int | None = None) -> Analysis:
    """Analyse every year (or just ``year``). Trends cover all years up to the last shown."""
    last = company.get(year).year if year is not None else company.years[-1].year
    upto = [fy for fy in company.years if fy.year <= last]
    results: list[YearResult] = []
    prev_values: dict[str, float | None] | None = None
    for fy in upto:
        prior = company.previous(fy.year)
        ratios = compute_ratios(fy)
        values = {r.key: r.value for group in ratios.values() for r in group}
        z = altman(fy)
        f_score = piotroski(fy, prior) if prior is not None else None
        flags = generate_flags(
            values,
            equity=fy.balance["total_equity"],
            prev=prev_values,
            altman=z,
            piotroski=f_score,
        )
        results.append(YearResult(fy.year, ratios, dupont(fy), z, f_score, flags))
        prev_values = values
    shown = [r for r in results if year is None or r.year == year]
    return Analysis(company, shown, compute_trends(upto))
