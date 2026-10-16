"""Plain-English flags."""

from __future__ import annotations

from statement_ratios.flags import generate_flags
from statement_ratios.scores import AltmanResult


def messages(values, **kwargs):
    kwargs.setdefault("equity", 100.0)
    return [f.message for f in generate_flags(values, **kwargs)]


def severities(values, **kwargs):
    kwargs.setdefault("equity", 100.0)
    return {f.severity for f in generate_flags(values, **kwargs)}


def test_thin_interest_coverage_flag_text():
    assert any(
        "interest coverage below 2x" in m and "thin buffer" in m
        for m in messages({"interest_coverage": 1.8})
    )


def test_very_low_interest_coverage_is_a_risk():
    assert "risk" in severities({"interest_coverage": 1.2})


def test_comfortable_coverage_is_good_and_mid_range_is_silent():
    assert "good" in severities({"interest_coverage": 10.0})
    assert messages({"interest_coverage": 4.0}) == []


def test_each_key_gets_at_most_one_tier():
    flags = generate_flags({"current_ratio": 0.8}, equity=100.0)
    assert len([f for f in flags if "current ratio" in f.message]) == 1


def test_current_ratio_tiers():
    assert "risk" in severities({"current_ratio": 0.9})
    assert "warning" in severities({"current_ratio": 1.2})
    assert "good" in severities({"current_ratio": 2.4})


def test_net_cash_flag():
    assert any("net cash" in m for m in messages({"net_debt_to_ebitda": -0.4}))


def test_negative_equity_flag():
    assert any("equity is zero or negative" in m for m in messages({}, equity=-5.0))


def test_earnings_quality_flag():
    assert "warning" in severities({"ocf_to_net_income": 0.5})


def test_gross_margin_drop_vs_prior_year():
    msgs = messages({"gross_margin": 0.30}, prev={"gross_margin": 0.35})
    assert any("gross margin fell 5.0 points" in m for m in msgs)


def test_missing_values_produce_no_flags():
    assert messages({"current_ratio": None, "interest_coverage": None}) == []


def test_flags_sorted_most_severe_first():
    flags = generate_flags({"current_ratio": 0.5, "roe": 0.30}, equity=100.0)
    assert [f.severity for f in flags] == ["risk", "good"]


def test_altman_distress_is_flagged_as_risk():
    z = AltmanResult(z=1.2, zone="distress", components={}, used_book_equity=False)
    flags = generate_flags({}, equity=100.0, altman=z)
    assert flags[0].severity == "risk"
    assert "1.20" in flags[0].message
