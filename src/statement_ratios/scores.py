"""Composite scores: Altman Z-score (original model) and Piotroski F-score."""

from __future__ import annotations

from dataclasses import dataclass

from .models import FiscalYear
from .ratios import gross_profit, safe_div

# ---- Altman Z-score ------------------------------------------------------------------------

ALTMAN_WEIGHTS: dict[str, float] = {
    "working_capital_to_assets": 1.2,
    "retained_earnings_to_assets": 1.4,
    "ebit_to_assets": 3.3,
    "equity_to_liabilities": 0.6,
    "sales_to_assets": 1.0,
}
ALTMAN_SAFE = 2.99
ALTMAN_DISTRESS = 1.81

ZONE_TEXT = {
    "safe": "Safe zone (low bankruptcy risk on this model)",
    "grey": "Grey zone (ambiguous, watch closely)",
    "distress": "Distress zone (elevated bankruptcy risk on this model)",
}

RATING_TEXT = {
    "strong": "Strong (financial position improving on most signals)",
    "moderate": "Moderate (mixed signals)",
    "weak": "Weak (most signals deteriorating)",
    "n/a": "n/a",
}


def altman_zone(z: float) -> str:
    """Classify a Z-score: above 2.99 safe, below 1.81 distress, otherwise grey."""
    if z > ALTMAN_SAFE:
        return "safe"
    if z < ALTMAN_DISTRESS:
        return "distress"
    return "grey"


def altman_zscore(x1: float, x2: float, x3: float, x4: float, x5: float) -> float:
    """Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5."""
    w = ALTMAN_WEIGHTS
    parts = (x1, x2, x3, x4, x5)
    return sum(weight * x for weight, x in zip(w.values(), parts, strict=True))


@dataclass(frozen=True)
class AltmanResult:
    z: float | None
    zone: str | None
    components: dict[str, float]
    used_book_equity: bool

    @property
    def interpretation(self) -> str:
        return ZONE_TEXT[self.zone] if self.zone else "n/a (needs positive assets and liabilities)"


def altman(fy: FiscalYear) -> AltmanResult:
    """Original (1968) Z-score for public manufacturers.

    X1 working capital / assets, X2 retained earnings / assets, X3 EBIT / assets,
    X4 market value of equity / total liabilities (book equity if no market value is
    given), X5 sales / assets.
    """
    bs = fy.balance
    assets, liabilities = bs["total_assets"], bs["total_liabilities"]
    market = bs.get("market_value_equity")
    equity_value = market if market is not None else bs["total_equity"]
    parts = {
        "working_capital_to_assets": safe_div(
            bs["current_assets"] - bs["current_liabilities"], assets, positive=True
        ),
        "retained_earnings_to_assets": safe_div(bs["retained_earnings"], assets, positive=True),
        "ebit_to_assets": safe_div(fy.income["operating_income"], assets, positive=True),
        "equity_to_liabilities": safe_div(equity_value, liabilities, positive=True),
        "sales_to_assets": safe_div(fy.income["revenue"], assets, positive=True),
    }
    used_book = market is None
    if any(v is None for v in parts.values()):
        return AltmanResult(None, None, {}, used_book)
    comps = {k: v for k, v in parts.items() if v is not None}
    z = altman_zscore(*comps.values())
    return AltmanResult(z, altman_zone(z), comps, used_book)


# ---- Piotroski F-score ---------------------------------------------------------------------


@dataclass(frozen=True)
class Criterion:
    key: str
    label: str
    passed: bool | None  # None = could not be evaluated
    detail: str


@dataclass(frozen=True)
class PiotroskiResult:
    criteria: tuple[Criterion, ...]

    @property
    def score(self) -> int:
        return sum(1 for c in self.criteria if c.passed)

    @property
    def max_score(self) -> int:
        return sum(1 for c in self.criteria if c.passed is not None)

    @property
    def rating(self) -> str:
        """strong (7/9 or better), moderate (4/9 or better), weak, or n/a."""
        if self.max_score == 0:
            return "n/a"
        if self.score * 9 >= 7 * self.max_score:
            return "strong"
        if self.score * 9 >= 4 * self.max_score:
            return "moderate"
        return "weak"

    @property
    def interpretation(self) -> str:
        return RATING_TEXT[self.rating]


def _check(key: str, label: str, passed: bool | None, detail: str) -> Criterion:
    return Criterion(key, label, passed, detail if passed is not None else "not computable")


def _improved(
    key: str, label: str, now: float | None, before: float | None, *, higher: bool = True
) -> Criterion:
    """Criterion passing when ``now`` is above (or, with higher=False, below) ``before``."""
    if now is None or before is None:
        return _check(key, label, None, "")
    passed = now > before if higher else now < before
    return _check(key, label, passed, f"{now:.4f} vs {before:.4f} prior year")


def piotroski(cur: FiscalYear, prev: FiscalYear) -> PiotroskiResult:
    """Piotroski's nine-point F-score comparing ``cur`` with the prior year ``prev``.

    Simplification: ratios use year-end total assets rather than beginning-of-year assets.
    Leverage is long-term debt / total assets; a company with no long-term debt passes.
    """

    def roa(fy: FiscalYear) -> float | None:
        return safe_div(fy.income["net_income"], fy.balance["total_assets"], positive=True)

    def leverage(fy: FiscalYear) -> float | None:
        return safe_div(fy.balance["long_term_debt"], fy.balance["total_assets"], positive=True)

    def current(fy: FiscalYear) -> float | None:
        return safe_div(fy.balance["current_assets"], fy.balance["current_liabilities"])

    def margin(fy: FiscalYear) -> float | None:
        return safe_div(gross_profit(fy), fy.income["revenue"])

    def turnover(fy: FiscalYear) -> float | None:
        return safe_div(fy.income["revenue"], fy.balance["total_assets"])

    ni, ocf = cur.income["net_income"], cur.cash_flow["operating_cash_flow"]
    roa_now, lev_now = roa(cur), leverage(cur)
    shares = cur.balance.get("shares_outstanding")
    shares_prev = prev.balance.get("shares_outstanding")
    diluted = None if shares is None or shares_prev is None else shares > shares_prev
    if lev_now == 0:
        lev_check = _check("leverage_down", "Leverage fell", True, "no long-term debt")
    else:
        lev_check = _improved(
            "leverage_down", "Leverage fell", lev_now, leverage(prev), higher=False
        )
    positive_roa = None if roa_now is None else roa_now > 0
    return PiotroskiResult(
        (
            _check("positive_roa", "ROA is positive", positive_roa, f"ROA {roa_now or 0:.4f}"),
            _check("positive_cfo", "Operating cash flow is positive", ocf > 0, f"OCF {ocf:,.0f}"),
            _improved("roa_up", "ROA improved", roa_now, roa(prev)),
            _check(
                "accruals",
                "Cash flow exceeds net income",
                ocf > ni,
                f"OCF {ocf:,.0f} vs NI {ni:,.0f}",
            ),
            lev_check,
            _improved("current_ratio_up", "Current ratio improved", current(cur), current(prev)),
            _check(
                "no_dilution",
                "No new shares issued",
                None if diluted is None else not diluted,
                f"{shares} vs {shares_prev} shares",
            ),
            _improved("gross_margin_up", "Gross margin improved", margin(cur), margin(prev)),
            _improved(
                "asset_turnover_up", "Asset turnover improved", turnover(cur), turnover(prev)
            ),
        )
    )
