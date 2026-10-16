"""DuPont decomposition: factors multiply back to ROE exactly."""

from __future__ import annotations

import pytest

from conftest import make_year
from statement_ratios.dupont import dupont


def test_three_step_factors_by_hand():
    d = dupont(make_year())
    assert d.three_step == pytest.approx(
        {"net_margin": 0.09, "asset_turnover": 1.0, "equity_multiplier": 2.5}
    )


def test_five_step_factors_by_hand():
    d = dupont(make_year())
    assert d.five_step == pytest.approx(
        {
            "tax_burden": 0.75,  # 90 / 120
            "interest_burden": 0.80,  # 120 / 150
            "operating_margin": 0.15,
            "asset_turnover": 1.0,
            "equity_multiplier": 2.5,
        }
    )


def test_identity_three_step_product_equals_roe():
    d = dupont(make_year())
    assert d.roe == pytest.approx(0.225)
    assert d.roe_three_step == pytest.approx(d.roe)


def test_identity_five_step_product_equals_roe():
    d = dupont(make_year())
    assert d.roe_five_step == pytest.approx(d.roe)


@pytest.mark.parametrize("year_name", ["acme_industrial", "nimbus_software"])
def test_identity_holds_on_example_files(year_name):
    from conftest import EXAMPLES
    from statement_ratios import load_company

    for fy in load_company(EXAMPLES / f"{year_name}.json").years:
        d = dupont(fy)
        assert d.roe_three_step == pytest.approx(d.roe)
        assert d.roe_five_step == pytest.approx(d.roe)


def test_identity_holds_with_awkward_numbers():
    fy = make_year(
        income_statement={
            "revenue": 731.5,
            "operating_income": 88.25,
            "income_before_tax": 70.1,
            "net_income": 52.3,
        },
        balance_sheet={"total_assets": 913.7, "total_equity": 311.9},
    )
    d = dupont(fy)
    assert d.roe_three_step == pytest.approx(52.3 / 311.9)
    assert d.roe_five_step == pytest.approx(52.3 / 311.9)


def test_negative_equity_gives_no_decomposition():
    d = dupont(make_year(balance_sheet={"total_equity": -50}))
    assert d.roe is None
    assert d.three_step is None
    assert d.five_step is None


def test_zero_operating_income_blocks_only_five_step():
    d = dupont(make_year(income_statement={"operating_income": 0}))
    assert d.three_step is not None
    assert d.five_step is None
