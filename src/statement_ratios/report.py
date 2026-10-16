"""Render an :class:`Analysis` as a terminal table, Markdown or JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from . import __version__
from .analysis import Analysis, YearResult
from .dupont import FIVE_STEP_FACTORS, THREE_STEP_FACTORS
from .ratios import Kind

NA = "n/a"
DISCLAIMER = (
    "Educational use only. Not investment advice. The original Altman model was fitted to "
    "public manufacturers, so treat its zones as indicative elsewhere."
)
FLAG_TAGS = {"risk": "RISK", "warning": "WARN", "info": "INFO", "good": "GOOD"}


def fmt_value(value: float | None, kind: Kind) -> str:
    """Format a number for display; None becomes 'n/a'."""
    if value is None:
        return NA
    if kind == "x":
        return f"{value:,.2f}x"
    if kind == "pct":
        return f"{value * 100:.1f}%"
    if kind == "days":
        return f"{value:.1f} d"
    return f"{value:,.0f}"


def _growth(value: float | None) -> str:
    return NA if value is None else f"{value * 100:+.1f}%"


@dataclass(frozen=True)
class Section:
    title: str
    columns: list[str]
    rows: list[tuple[str, list[str]]]


def _factor_rows(
    results: list[YearResult],
    factors: tuple[tuple[str, str, Kind], ...],
    attr: str,
    total_label: str,
) -> list[tuple[str, list[str]]]:
    rows = []
    for key, label, kind in factors:
        cells = []
        for res in results:
            parts = getattr(res.dupont, attr)
            cells.append(fmt_value(parts[key] if parts else None, kind))
        rows.append((label, cells))
    product = "roe_three_step" if attr == "three_step" else "roe_five_step"
    rows.append((total_label, [fmt_value(getattr(r.dupont, product), "pct") for r in results]))
    return rows


def build_sections(analysis: Analysis) -> list[Section]:
    results = analysis.results
    cols = [str(r.year) for r in results]
    sections: list[Section] = []
    for category, group in results[0].ratios.items():
        rows = [
            (ratio.label, [fmt_value(r.ratios[category][i].value, ratio.kind) for r in results])
            for i, ratio in enumerate(group)
        ]
        sections.append(Section(category, cols, rows))
    sections.append(
        Section(
            "DuPont: 3-step", cols, _factor_rows(results, THREE_STEP_FACTORS, "three_step", "= ROE")
        )
    )
    sections.append(
        Section(
            "DuPont: 5-step", cols, _factor_rows(results, FIVE_STEP_FACTORS, "five_step", "= ROE")
        )
    )
    score_rows = [
        ("Altman Z-score", [NA if r.altman.z is None else f"{r.altman.z:.2f}" for r in results]),
        ("Altman zone", [r.altman.zone or NA for r in results]),
        (
            "Piotroski F-score",
            [
                NA
                if r.piotroski is None or not r.piotroski.max_score
                else f"{r.piotroski.score}/{r.piotroski.max_score}"
                for r in results
            ],
        ),
        ("Piotroski reading", [NA if r.piotroski is None else r.piotroski.rating for r in results]),
    ]
    sections.append(Section("Scores", cols, score_rows))
    last = results[-1]
    if last.piotroski is not None:
        rows = [
            (c.label, [NA if c.passed is None else ("PASS" if c.passed else "FAIL")])
            for c in last.piotroski.criteria
        ]
        sections.append(Section(f"Piotroski criteria ({last.year})", ["Result"], rows))
    if analysis.trends:
        first_year = analysis.trends[0].values
        span = f"{min(first_year)}-{max(first_year)}"
        trend_rows = [
            (
                t.label,
                [_growth(t.yoy[r.year]) if r.year in t.yoy else "-" for r in results]
                + [_growth(t.cagr)],
            )
            for t in analysis.trends
        ]
        sections.append(Section("Growth (year over year)", [*cols, f"CAGR {span}"], trend_rows))
    return sections


def _header_lines(analysis: Analysis) -> list[str]:
    c = analysis.company
    years = [r.year for r in analysis.results]
    span = str(years[0]) if len(years) == 1 else f"{years[0]}-{years[-1]}"
    meta = f"Currency: {c.currency}" + (f" ({c.units})" if c.units else "") + f" | FY {span}"
    lines = [c.name + ("  [SYNTHETIC EXAMPLE DATA]" if c.synthetic else ""), meta]
    if c.note:
        lines.append(c.note)
    return lines


def _flag_title(analysis: Analysis) -> str:
    return f"Flags (FY{analysis.results[-1].year})"


def _line(label: str, cells: list[str], label_w: int, widths: list[int]) -> str:
    padded = "".join(f"  {v:>{w}}" for v, w in zip(cells, widths, strict=True))
    return f"  {label:<{label_w}}{padded}"


def render_table(analysis: Analysis) -> str:
    """Plain-text report with aligned columns."""
    out = _header_lines(analysis)
    for sec in build_sections(analysis):
        label_w = max(len(label) for label, _ in sec.rows)
        widths = [
            max(len(col), *(len(cells[i]) for _, cells in sec.rows))
            for i, col in enumerate(sec.columns)
        ]
        out += ["", sec.title.upper()]
        head = _line("", sec.columns, label_w, widths)
        out += [head, "  " + "-" * (len(head) - 2)]
        out += [_line(label, cells, label_w, widths) for label, cells in sec.rows]
    out += ["", _flag_title(analysis).upper()]
    flags = analysis.results[-1].flags
    out += [f"  [{FLAG_TAGS[f.severity]}] {f.message}" for f in flags] or ["  (none)"]
    out += ["", DISCLAIMER]
    return "\n".join(out) + "\n"


def render_markdown(analysis: Analysis) -> str:
    """Markdown report with one table per section."""
    c = analysis.company
    head = _header_lines(analysis)
    out = [f"# Ratio analysis: {c.name}", ""]
    if c.synthetic:
        out += ["> **Synthetic example data.** This company is fictional.", ""]
    out += [head[1]] + ([f"\n{c.note}"] if c.note else [])
    for sec in build_sections(analysis):
        out += ["", f"## {sec.title}", ""]
        out.append("| Metric | " + " | ".join(sec.columns) + " |")
        out.append("|---|" + "---:|" * len(sec.columns))
        out += [f"| {label} | " + " | ".join(cells) + " |" for label, cells in sec.rows]
    out += ["", f"## {_flag_title(analysis)}", ""]
    flags = analysis.results[-1].flags
    out += [f"- **{FLAG_TAGS[f.severity]}** ({f.area}): {f.message}" for f in flags] or ["- none"]
    out += ["", f"_{DISCLAIMER}_"]
    return "\n".join(out) + "\n"


def _year_dict(r: YearResult) -> dict[str, Any]:
    f_score = r.piotroski
    return {
        "year": r.year,
        "ratios": {cat: [asdict(x) for x in group] for cat, group in r.ratios.items()},
        "dupont": asdict(r.dupont),
        "altman": asdict(r.altman),
        "piotroski": None
        if f_score is None
        else {
            "score": f_score.score,
            "max_score": f_score.max_score,
            "rating": f_score.rating,
            "criteria": [asdict(k) for k in f_score.criteria],
        },
        "flags": [asdict(f) for f in r.flags],
    }


def to_dict(analysis: Analysis) -> dict[str, Any]:
    """Machine-readable form of the whole analysis (None values become null)."""
    c = analysis.company
    return {
        "tool": f"statement-ratios {__version__}",
        "company": c.name,
        "currency": c.currency,
        "units": c.units,
        "synthetic": c.synthetic,
        "years": [_year_dict(r) for r in analysis.results],
        "trends": [
            {
                "key": t.key,
                "label": t.label,
                "values": {str(y): v for y, v in t.values.items()},
                "yoy": {str(y): v for y, v in t.yoy.items()},
                "cagr": t.cagr,
            }
            for t in analysis.trends
        ],
        "disclaimer": DISCLAIMER,
    }


def render_json(analysis: Analysis) -> str:
    return json.dumps(to_dict(analysis), indent=2, allow_nan=False) + "\n"


RENDERERS = {"table": render_table, "markdown": render_markdown, "json": render_json}
