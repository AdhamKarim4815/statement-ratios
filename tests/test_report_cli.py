"""Reports, JSON output and the command line."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import EXAMPLES
from statement_ratios import analyze, build_company, load_company
from statement_ratios.cli import main
from statement_ratios.report import fmt_value, render_json, render_markdown, render_table
from statement_ratios.schema import template

ACME = str(EXAMPLES / "acme_industrial.json")
NIMBUS = str(EXAMPLES / "nimbus_software.json")
SRC = Path(__file__).resolve().parent.parent / "src"


def run(capsys, *args):
    code = main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_fmt_value_by_kind():
    assert fmt_value(1.5, "x") == "1.50x"
    assert fmt_value(0.123, "pct") == "12.3%"
    assert fmt_value(45.04, "days") == "45.0 d"
    assert fmt_value(12345.6, "money") == "12,346"
    assert fmt_value(None, "x") == "n/a"


def test_table_output_for_acme(capsys):
    code, out, _ = run(capsys, "analyze", ACME)
    assert code == 0
    assert "Acme Industrial Co.  [SYNTHETIC EXAMPLE DATA]" in out
    assert "Current ratio" in out
    assert "DUPONT: 5-STEP" in out
    assert "Altman Z-score" in out
    assert "FLAGS (FY2024)" in out


def test_markdown_output(capsys):
    code, out, _ = run(capsys, "analyze", ACME, "--format", "markdown")
    assert code == 0
    assert out.startswith("# Ratio analysis: Acme Industrial Co.")
    assert "| Metric | 2022 | 2023 | 2024 |" in out
    assert "## Flags (FY2024)" in out


def test_json_output_is_valid_and_complete(capsys):
    code, out, _ = run(capsys, "analyze", ACME, "--format", "json")
    assert code == 0
    data = json.loads(out)
    assert [y["year"] for y in data["years"]] == [2022, 2023, 2024]
    assert data["synthetic"] is True
    assert data["years"][0]["piotroski"] is None
    assert data["years"][2]["piotroski"]["score"] == 9
    assert {t["key"] for t in data["trends"]} >= {"revenue", "net_income"}


def test_json_values_match_direct_calculation(capsys):
    _, out, _ = run(capsys, "analyze", ACME, "--format", "json", "--year", "2024")
    data = json.loads(out)
    ratios = {r["key"]: r["value"] for r in data["years"][0]["ratios"]["Liquidity"]}
    # Acme 2024: current assets 345,000 / current liabilities 135,000
    assert ratios["current_ratio"] == pytest.approx(345000 / 135000)


def test_year_option_limits_output(capsys):
    _, out, _ = run(capsys, "analyze", ACME, "--year", "2023")
    assert "FLAGS (FY2023)" in out
    assert "CAGR 2022-2023" in out
    data = json.loads(run(capsys, "analyze", ACME, "--format", "json", "--year", "2023")[1])
    assert [y["year"] for y in data["years"]] == [2023]


def test_first_year_has_no_piotroski_score():
    result = analyze(load_company(ACME), year=2022)
    assert result.results[0].piotroski is None
    assert result.trends == []


def test_unknown_year_is_a_clean_error(capsys):
    code, out, err = run(capsys, "analyze", ACME, "--year", "1999")
    assert code == 1
    assert out == ""
    assert "year 1999 not found" in err


def test_missing_file_is_a_clean_error(capsys):
    code, _, err = run(capsys, "analyze", "/no/such/file.json")
    assert code == 1
    assert err.startswith("error: file not found")


def test_validation_errors_listed_on_stderr(tmp_path, capsys):
    raw = template()
    del raw["years"][0]["income_statement"]["revenue"]
    del raw["years"][1]["balance_sheet"]["cash"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw))
    code, _, err = run(capsys, "analyze", str(path))
    assert code == 1
    assert "2 problems found" in err
    assert "income_statement.revenue is missing" in err


def test_schema_command_prints_reference_and_template(capsys):
    code, out, _ = run(capsys, "schema")
    assert code == 0
    assert "income_statement:" in out
    assert "required" in out and "optional" in out
    assert json.loads(out[out.index("{") :])["company"] == "Example Co."


def test_schema_template_only_is_pure_json_and_valid(capsys):
    code, out, _ = run(capsys, "schema", "--template")
    assert code == 0
    company = build_company(json.loads(out))
    assert company.year_numbers == [2023, 2024]
    assert analyze(company).results[-1].piotroski is not None


def test_nimbus_example_handles_na_values_gracefully():
    result = analyze(load_company(NIMBUS), year=2022)
    values = result.results[0].values()
    assert values["inventory_turnover"] is None
    assert values["net_debt_to_ebitda"] is None
    assert values["ocf_to_net_income"] is None
    text = render_table(result)
    assert "n/a" in text


@pytest.mark.parametrize("path", [ACME, NIMBUS])
def test_every_format_renders_for_each_example(path):
    result = analyze(load_company(path))
    for render in (render_table, render_markdown, render_json):
        assert render(result).strip()


@pytest.mark.parametrize("path", [ACME, NIMBUS])
def test_examples_are_labelled_synthetic(path):
    company = load_company(path)
    assert company.synthetic is True
    assert "SYNTHETIC" in render_table(analyze(company))


@pytest.mark.parametrize("fmt", ["table", "markdown", "json"])
def test_no_dashes_in_output(fmt, capsys):
    _, out, _ = run(capsys, "analyze", NIMBUS, "--format", fmt)
    assert chr(0x2013) not in out
    assert chr(0x2014) not in out


def test_module_entry_point_runs_as_subprocess():
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.run(
        [sys.executable, "-m", "statement_ratios", "analyze", ACME, "--year", "2024"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0
    assert "Acme Industrial Co." in proc.stdout


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert "0.1.0" in capsys.readouterr().out
