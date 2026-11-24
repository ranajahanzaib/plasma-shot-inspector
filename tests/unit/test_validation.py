import numpy as np
import pytest

from plasma_inspector.models import Outcome
from plasma_inspector.validation.signal import inspect_signal
from plasma_inspector.validation.time_axis import inspect_time_axis


def test_time_axis_keeps_negative_pretrigger_times_and_checks_order():
    result, findings = inspect_time_axis(np.array([-0.1, -0.05, 0.0, 0.0, -0.02]))
    assert result.negative_time_count == 3
    assert result.duplicate_count == 1
    assert result.nonmonotonic_count == 1
    assert all(f.outcome == Outcome.FAIL for f in findings)


def test_missing_signal_values_are_not_repaired():
    stats, findings = inspect_signal(np.array([1.0, np.nan, 3.0]), name="current", units="A")
    assert stats["finite_count"] == 2
    assert stats["missing_fraction"] == pytest.approx(1 / 3)
    assert any(f.outcome == Outcome.WARNING for f in findings)


def test_constant_signal_is_an_inspection_candidate():
    _, findings = inspect_signal(np.ones(8), name="ip")
    assert any(f.rule_id == "SIGNAL-FLAT-001" and f.outcome == Outcome.WARNING for f in findings)


def test_time_axis_reports_reversed_transitions_and_large_gaps_without_bridging_nan():
    result, findings = inspect_time_axis(np.array([0.0, 1.0, 2.0, 20.0, np.nan, 19.0, 18.0]))
    by_rule = {finding.rule_id: finding for finding in findings}

    assert result.nonmonotonic_count == 1
    assert by_rule["TIME-GAP-001"].evidence["count"] == 1
    assert by_rule["TIME-ORDER-001"].evidence["transitions"][-1]["left_time"] == 19.0


def test_signal_reports_missing_intervals_flatlines_and_isolated_spikes_as_candidates():
    values = np.tile([0.0, 1.0], 20)
    values[10:20] = 4.0
    values[30] = 40.0
    values[4:7] = np.nan
    _, findings = inspect_signal(values, name="fixture", time=np.arange(values.size, dtype=float))
    by_rule = {finding.rule_id: finding for finding in findings}

    assert by_rule["SIGNAL-FINITE-001"].evidence["longest_missing_run"] == 3
    assert by_rule["SIGNAL-FINITE-001"].evidence["missing_runs"][0]["start_time"] == 4.0
    assert by_rule["SIGNAL-FLATLINE-002"].outcome == Outcome.WARNING
    assert by_rule["SIGNAL-SPIKE-001"].evidence["sample_indices"] == [30]
