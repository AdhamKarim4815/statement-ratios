"""DuPont decomposition of return on equity (3-step and 5-step)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import FiscalYear
from .ratios import Kind, safe_div

THREE_STEP_FACTORS: tuple[tuple[str, str, Kind], ...] = (
    ("net_margin", "Net profit margin", "pct"),
    ("asset_turnover", "Asset turnover", "x"),
    ("equity_multiplier", "Equity multiplier", "x"),
)
FIVE_STEP_FACTORS: tuple[tuple[str, str, Kind], ...] = (
    ("tax_burden", "Tax burden (NI / EBT)", "x"),
    ("interest_burden", "Interest burden (EBT / EBIT)", "x"),
    ("operating_margin", "Operating margin", "pct"),
    ("asset_turnover", "Asset turnover", "x"),
    ("equity_multiplier", "Equity multiplier", "x"),
)


def _product(factors: dict[str, float] | None) -> float | None:
    if factors is None:
        return None
    result = 1.0
    for value in factors.values():
        result *= value
    return result


@dataclass(frozen=True)
class DuPont:
    """ROE and its factors. Factor dicts are None when any factor is undefined."""

    roe: float | None
    three_step: dict[str, float] | None = field(default=None)
    five_step: dict[str, float] | None = field(default=None)

    @property
    def roe_three_step(self) -> float | None:
        """ROE rebuilt as the product of the 3-step factors (equals ``roe``)."""
        return _product(self.three_step)

    @property
    def roe_five_step(self) -> float | None:
        """ROE rebuilt as the product of the 5-step factors (equals ``roe``)."""
        return _product(self.five_step)


def _collect(parts: dict[str, float | None]) -> dict[str, float] | None:
    if any(v is None for v in parts.values()):
        return None
    return {k: v for k, v in parts.items() if v is not None}


def dupont(fy: FiscalYear) -> DuPont:
    """Decompose ROE.

    3-step: net margin x asset turnover x equity multiplier.
    5-step: tax burden x interest burden x operating margin x asset turnover x multiplier.
    Both equal NI / equity exactly; undefined (None) on non-positive equity or zero bases.
    """
    inc, bs = fy.income, fy.balance
    equity = bs["total_equity"]
    revenue, assets = inc["revenue"], bs["total_assets"]
    ni, ebt, ebit = inc["net_income"], inc["income_before_tax"], inc["operating_income"]
    roe = safe_div(ni, equity, positive=True)
    margin = safe_div(ni, revenue)
    turnover = safe_div(revenue, assets)
    multiplier = safe_div(assets, equity, positive=True)
    three = _collect(
        {"net_margin": margin, "asset_turnover": turnover, "equity_multiplier": multiplier}
    )
    five = _collect(
        {
            "tax_burden": safe_div(ni, ebt),
            "interest_burden": safe_div(ebt, ebit),
            "operating_margin": safe_div(ebit, revenue),
            "asset_turnover": turnover,
            "equity_multiplier": multiplier,
        }
    )
    return DuPont(roe=roe, three_step=three, five_step=five)
