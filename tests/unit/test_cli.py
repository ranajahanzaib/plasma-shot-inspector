import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from plasma_inspector.cli import app

runner = CliRunner()


def test_cli_rules_list() -> None:
    result = runner.invoke(app, ["rules", "list"])
    assert result.exit_code == 0
    rules = json.loads(result.output)
    assert isinstance(rules, list)
    rule_ids = {r["id"] for r in rules}
    assert "TIME-STRUCTURE-001" in rule_ids
    assert "SIGNAL-FINITE-001" in rule_ids
    assert "EQ-GRID-001" in rule_ids


def test_cli_catalog_search_json() -> None:
    mock_rows = [
        {
            "shot_id": 11766,
            "campaign": "M5",
            "timestamp": "2005-01-13 12:02:00",
            "plasma_max_current": 500.63,
            "divertor_config": "Conventional",
            "shot_summary": "Test shot summary",
            "extra_field": "hidden_by_default",
        }
    ]
    with patch("plasma_inspector.cli.FairMastAdapter") as mock_adapter_cls:
        mock_instance = MagicMock()
        mock_instance.list_shots.return_value = mock_rows
        mock_adapter_cls.return_value = mock_instance

        result = runner.invoke(app, ["catalog", "search", "--level", "2", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 1
        assert parsed[0]["shot_id"] == 11766


def test_cli_catalog_search_table_formatting() -> None:
    mock_rows = [
        {
            "shot_id": 11766,
            "campaign": "M5",
            "timestamp": "2005-01-13 12:02:00",
            "plasma_max_current": 500.6307,
            "divertor_config": "Conventional",
            "shot_summary": "COMMISSIONED ENGINEERING PLASMA",
            "extra_col": "should_not_show",
        }
    ]
    with patch("plasma_inspector.cli.FairMastAdapter") as mock_adapter_cls:
        mock_instance = MagicMock()
        mock_instance.list_shots.return_value = mock_rows
        mock_adapter_cls.return_value = mock_instance

        result = runner.invoke(app, ["catalog", "search", "--level", "2", "--limit", "5"])
        assert result.exit_code == 0
        assert "FAIR-MAST Level 2 Catalog (1 shots)" in result.output
        assert "11766" in result.output
        assert "M5" in result.output
        assert "500.63" in result.output
        assert "Conventional" in result.output


def test_cli_catalog_search_empty_result() -> None:
    with patch("plasma_inspector.cli.FairMastAdapter") as mock_adapter_cls:
        mock_instance = MagicMock()
        mock_instance.list_shots.return_value = []
        mock_adapter_cls.return_value = mock_instance

        result = runner.invoke(app, ["catalog", "search", "--level", "2", "--q", "999999"])
        assert result.exit_code == 0
        assert "No shots found" in result.output
