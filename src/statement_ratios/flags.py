"""Short plain-English flags derived from ratios and scores."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .scores import AltmanResult, PiotroskiResult

Severity = Literal["good", "info", "warning", "risk"]
SEVERITY_ORDER: dict[str, int] = {"risk": 0, "warning": 1, "info": 2, "good": 3}
ZONE_SEVERITY: dict[str, Severity] = {"safe": "good", "grey": "warning", "distress": "risk"}
RATING_SEVERITY: dict[str, Severity] = {"strong": "good", "moderate": "info", "weak": "warning"}


@dataclass(frozen=True)
class Flag:
    severity: Severity
    area: str
    message: str


# (ratio key, test, severity, area, message). For each key the first matching rule wins,
# so tiers are listed from most to least severe. Thresholds are common rules of thumb.
Rule = tuple[str, Callable[[float], bool], Severity, str, Callable[[float], str]]
# fmt: off
RULES: tuple[Rule, ...] = (
    ("current_ratio", lambda v: v < 1.0, "risk", "Liquidity",
     lambda v: f"current ratio below 1.0x ({v:.2f}x): short-term debts exceed current assets"),
    ("current_ratio", lambda v: v < 1.5, "warning", "Liquidity",
     lambda v: f"current ratio below 1.5x ({v:.2f}x): limited cushion"),
    ("current_ratio", lambda v: v >= 2.0, "good", "Liquidity",
     lambda v: f"current ratio of {v:.2f}x: comfortable liquidity"),
    ("quick_ratio", lambda v: v < 0.5, "warning", "Liquidity",
     lambda v: f"quick ratio below 0.5x ({v:.2f}x): leans on inventory sales for near-term bills"),
    ("interest_coverage", lambda v: v < 1.5, "risk", "Leverage",
     lambda v: f"interest coverage below 1.5x ({v:.2f}x): operating profit barely covers interest"),
    ("interest_coverage", lambda v: v < 2.0, "warning", "Leverage",
     lambda v: f"interest coverage below 2x ({v:.2f}x): thin buffer"),
    ("interest_coverage", lambda v: v >= 8.0, "good", "Leverage",
     lambda v: f"interest coverage of {v:.1f}x: debt service is comfortable"),
    ("debt_to_equity", lambda v: v > 2.0, "warning", "Leverage",
     lambda v: f"debt/equity above 2.0x ({v:.2f}x): heavy use of borrowing"),
    ("net_debt_to_ebitda", lambda v: v > 4.0, "risk", "Leverage",
     lambda v: f"net debt/EBITDA above 4x ({v:.1f}x): very high leverage"),
    ("net_debt_to_ebitda", lambda v: v > 3.0, "warning", "Leverage",
     lambda v: f"net debt/EBITDA above 3x ({v:.1f}x): elevated leverage"),
    ("net_debt_to_ebitda", lambda v: v < 0, "good", "Leverage",
     lambda v: "net cash position: cash and investments exceed debt"),
    ("net_margin", lambda v: v < 0, "risk", "Profitability",
     lambda v: f"net loss (net margin {v * 100:.1f}%)"),
    ("roe", lambda v: v >= 0.15, "good", "Profitability",
     lambda v: f"ROE of {v * 100:.1f}%: strong return on equity"),
    ("roic", lambda v: v < 0.08, "warning", "Profitability",
     lambda v: f"ROIC below 8% ({v * 100:.1f}%): may not cover a typical cost of capital"),
    ("roic", lambda v: v >= 0.15, "good", "Profitability",
     lambda v: f"ROIC of {v * 100:.1f}%: well above a typical cost of capital"),
    ("ocf_to_net_income", lambda v: v < 0.8, "warning", "Cash flow",
     lambda v: f"operating cash flow is {v:.2f}x net income: earnings quality is worth checking"),
    ("ocf_to_net_income", lambda v: v >= 1.0, "good", "Cash flow",
     lambda v: f"operating cash flow is {v:.2f}x net income: earnings are backed by cash"),
    ("free_cash_flow", lambda v: v < 0, "warning", "Cash flow",
     lambda v: "negative free cash flow: capex exceeds operating cash flow"),
    ("cash_conversion_cycle", lambda v: v > 90, "warning", "Efficiency",
     lambda v: f"cash conversion cycle of {v:.0f} days: cash is tied up for a long time"),
    ("cash_conversion_cycle", lambda v: v < 0, "good", "Efficiency",
     lambda v: "negative cash conversion cycle: suppliers fund operations"),
)
# fmt: on


def generate_flags(
    values: dict[str, float | None],
    *,
    equity: float,
    prev: dict[str, float | None] | None = None,
    altman: AltmanResult | None = None,
    piotroski: PiotroskiResult | None = None,
) -> list[Flag]:
    """Apply threshold rules to ``values`` (ratio key to value) and the composite scores."""
    flags: list[Flag] = []
    matched: set[str] = set()
    if equity <= 0:
        msg = "equity is zero or negative: ROE and debt/equity are not meaningful"
        flags.append(Flag("risk", "Leverage", msg))
    for key, test, severity, area, message in RULES:
        value = values.get(key)
        if value is not None and key not in matched and test(value):
            matched.add(key)
            flags.append(Flag(severity, area, message(value)))
    before = prev or {}
    gm, gm_prev = values.get("gross_margin"), before.get("gross_margin")
    if gm is not None and gm_prev is not None:
        delta = (gm - gm_prev) * 100
        if delta <= -2.0:
            msg = f"gross margin fell {-delta:.1f} points year on year"
            flags.append(Flag("warning", "Profitability", msg))
        elif delta >= 2.0:
            msg = f"gross margin rose {delta:.1f} points year on year"
            flags.append(Flag("good", "Profitability", msg))
    dso, dso_prev = values.get("receivables_days"), before.get("receivables_days")
    if dso is not None and dso_prev and dso / dso_prev > 1.15:
        msg = f"receivables days up {(dso / dso_prev - 1) * 100:.0f}% YoY: check collections"
        flags.append(Flag("warning", "Efficiency", msg))
    if altman is not None and altman.z is not None and altman.zone is not None:
        msg = f"Altman Z-score {altman.z:.2f}: {altman.interpretation.lower()}"
        flags.append(Flag(ZONE_SEVERITY[altman.zone], "Scores", msg))
    if piotroski is not None and piotroski.max_score:
        msg = f"Piotroski F-score {piotroski.score}/{piotroski.max_score}: "
        msg += piotroski.interpretation.lower()
        flags.append(Flag(RATING_SEVERITY[piotroski.rating], "Scores", msg))
    return sorted(flags, key=lambda f: SEVERITY_ORDER[f.severity])
