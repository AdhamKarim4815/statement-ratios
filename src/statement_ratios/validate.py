"""Validate raw (JSON-like) input and build a :class:`Company`."""

from __future__ import annotations

import difflib
import math
from collections.abc import Iterable
from typing import Any

from .models import BALANCE, STATEMENTS, Company, FiscalYear, ValidationError
from .schema import SCHEMA, TOP_LEVEL_KEYS

DEFAULT_TOLERANCE = 0.005  # balance sheet may be off by 0.5% of total assets


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _unknown(kind: str, key: str, valid: Iterable[str]) -> str:
    close = difflib.get_close_matches(key, list(valid), n=1)
    hint = f" (did you mean '{close[0]}'?)" if close else ""
    return f"unknown {kind} '{key}'{hint}"


def _parse_section(raw: Any, stmt: str, label: str, errors: list[str]) -> dict[str, float]:
    if raw is None:
        errors.append(f"{label}: section '{stmt}' is missing")
        return {}
    if not isinstance(raw, dict):
        errors.append(f"{label}: section '{stmt}' must be an object of line items")
        return {}
    out: dict[str, float] = {}
    for spec in SCHEMA[stmt]:
        value = raw.get(spec.name)
        where = f"{label}: {stmt}.{spec.name}"
        if value is None:
            if spec.required:
                errors.append(f"{where} is missing ({spec.description})")
            continue
        if not _is_number(value) or not math.isfinite(value):
            errors.append(f"{where} must be a finite number (got {value!r})")
        elif value < 0 and not spec.signed:
            errors.append(f"{where} must not be negative (got {value})")
        else:
            out[spec.name] = float(value)
    known = {spec.name for spec in SCHEMA[stmt]}
    errors.extend(
        f"{label}: {_unknown(f'field in {stmt}', key, known)}" for key in raw if key not in known
    )
    return out


def _check_balance_sheet(label: str, bs: dict[str, float], tolerance: float) -> list[str]:
    problems: list[str] = []
    assets = bs["total_assets"]
    slack = tolerance * abs(assets)
    liquid = (
        bs["cash"] + bs.get("short_term_investments", 0.0) + bs["receivables"] + bs["inventory"]
    )
    if liquid > bs["current_assets"] + slack:
        problems.append(
            f"{label}: cash + short-term investments + receivables + inventory ({liquid:,.0f}) "
            f"exceeds current_assets ({bs['current_assets']:,.0f})"
        )
    if bs["current_assets"] > assets + slack:
        problems.append(f"{label}: current_assets exceeds total_assets")
    if bs["current_liabilities"] > bs["total_liabilities"] + slack:
        problems.append(f"{label}: current_liabilities exceeds total_liabilities")
    claims = bs["total_liabilities"] + bs["total_equity"]
    diff = abs(assets - claims)
    if diff > slack:
        pct = diff / abs(assets) * 100 if assets else float("inf")
        problems.append(
            f"{label}: balance sheet does not balance: total_assets {assets:,.0f} vs "
            f"total_liabilities + total_equity {claims:,.0f} (off by {diff:,.0f}, "
            f"{pct:.2f}% of assets; tolerance {tolerance * 100:.2f}%)"
        )
    return problems


def _parse_year(entry: Any, idx: int, tolerance: float, errors: list[str]) -> FiscalYear | None:
    where = f"years[{idx}]"
    if not isinstance(entry, dict):
        errors.append(f"{where} must be an object")
        return None
    year = entry.get("year")
    year_ok = isinstance(year, int) and not isinstance(year, bool)
    label = f"FY{year}" if year_ok else where
    if not year_ok:
        errors.append(f"{where}.year must be an integer (got {year!r})")
    before = len(errors)
    sections = {stmt: _parse_section(entry.get(stmt), stmt, label, errors) for stmt in STATEMENTS}
    allowed = ("year", *STATEMENTS)
    errors.extend(
        f"{label}: {_unknown('key', key, allowed)}" for key in entry if key not in allowed
    )
    if len(errors) > before or not year_ok:
        return None
    problems = _check_balance_sheet(label, sections[BALANCE], tolerance)
    errors.extend(problems)
    if problems:
        return None
    return FiscalYear(
        year=int(year),
        income=sections["income_statement"],
        balance=sections[BALANCE],
        cash_flow=sections["cash_flow"],
    )


def build_company(raw: Any, tolerance: float = DEFAULT_TOLERANCE) -> Company:
    """Validate ``raw`` and return a :class:`Company`, or raise :class:`ValidationError`."""
    if not isinstance(raw, dict):
        raise ValidationError(["top level must be an object with 'company' and 'years'"])
    errors: list[str] = [
        _unknown("top-level key", key, TOP_LEVEL_KEYS) for key in raw if key not in TOP_LEVEL_KEYS
    ]
    name = raw.get("company")
    if not isinstance(name, str) or not name.strip():
        errors.append("'company' must be a non-empty string")
    for key in ("currency", "units", "note"):
        if key in raw and not isinstance(raw[key], str):
            errors.append(f"'{key}' must be a string")
    if "synthetic" in raw and not isinstance(raw["synthetic"], bool):
        errors.append("'synthetic' must be true or false")
    entries = raw.get("years")
    years: list[FiscalYear] = []
    if not isinstance(entries, list) or not entries:
        errors.append("'years' must be a non-empty list")
    else:
        for idx, entry in enumerate(entries):
            fy = _parse_year(entry, idx, tolerance, errors)
            if fy is not None:
                years.append(fy)
        numbers = sorted(fy.year for fy in years)
        if len(set(numbers)) != len(numbers):
            errors.append("duplicate fiscal year in 'years'")
        elif numbers and numbers != list(range(numbers[0], numbers[-1] + 1)):
            errors.append("fiscal years must be consecutive (a year is missing)")
    if errors:
        raise ValidationError(errors)
    return Company(
        name=str(name).strip(),
        years=tuple(sorted(years, key=lambda fy: fy.year)),
        currency=str(raw.get("currency", "USD")),
        units=str(raw.get("units", "")),
        synthetic=bool(raw.get("synthetic", False)),
        note=str(raw.get("note", "")),
    )
