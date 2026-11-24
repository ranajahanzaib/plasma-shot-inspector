from __future__ import annotations

import numpy as np

from plasma_inspector.models import Finding, Outcome, Severity


def inspect_signal(
    values: np.ndarray, *, name: str, units: str | None = None,
    source: str | None = None, time: np.ndarray | None = None,
) -> tuple[dict, list[Finding]]:
    """Summarize samples without repair; statistical findings remain review candidates."""
    array = np.asarray(values)
    numeric = np.asarray(array, dtype=float).reshape(-1)
    finite = numeric[np.isfinite(numeric)]
    missing_runs = _runs(~np.isfinite(numeric))
    flatline_runs = _constant_runs(numeric)
    spike_indices = _isolated_spikes(numeric)
    stats: dict = {"name": name, "units": units, "sample_count": int(numeric.size),
        "finite_count": int(finite.size), "missing_fraction": float(1 - finite.size / numeric.size) if numeric.size else None,
        "longest_missing_run": max((end - start for start, end in missing_runs), default=0),
        "longest_constant_run": max((end - start for start, end in flatline_runs), default=0),
        "isolated_spike_candidate_count": len(spike_indices)}
    if finite.size:
        stats.update(min=float(np.min(finite)), max=float(np.max(finite)), mean=float(np.mean(finite)),
            median=float(np.median(finite)), std=float(np.std(finite)),
            mad=float(np.median(np.abs(finite - np.median(finite)))),
            percentiles={str(p): float(np.percentile(finite, p)) for p in (1, 5, 25, 75, 95, 99)})
    findings = []
    if not numeric.size:
        findings.append(Finding(rule_id="SIGNAL-EMPTY-001", outcome=Outcome.FAIL, severity=Severity.HIGH,
            summary=f"{name} is empty", explanation="The source array has no samples.", evidence=stats, source=source))
    elif finite.size != numeric.size:
        aligned_time = np.asarray(time, dtype=float).reshape(-1) if time is not None else np.asarray([])
        timed_runs = [
            {"start_index": start, "end_index": end - 1,
             "start_time": float(aligned_time[start]) if aligned_time.size == numeric.size and np.isfinite(aligned_time[start]) else None,
             "end_time": float(aligned_time[end - 1]) if aligned_time.size == numeric.size and np.isfinite(aligned_time[end - 1]) else None}
            for start, end in missing_runs[:20]
        ]
        findings.append(Finding(rule_id="SIGNAL-FINITE-001", outcome=Outcome.WARNING, severity=Severity.MEDIUM,
            summary=f"{name} contains missing or nonfinite samples", explanation="Original values are retained; no imputation was performed.", evidence={**stats, "missing_runs": timed_runs}, source=source))
    if finite.size and np.ptp(finite) == 0:
        findings.append(Finding(rule_id="SIGNAL-FLAT-001", outcome=Outcome.WARNING, severity=Severity.LOW,
            summary=f"{name} is constant", explanation="A constant interval can be valid; inspect signal context before interpreting it as a fault.", evidence=stats, source=source))
    elif flatline_runs:
        longest = max(flatline_runs, key=lambda run: run[1] - run[0])
        if longest[1] - longest[0] >= 8:
            aligned_time = np.asarray(time, dtype=float).reshape(-1) if time is not None else np.asarray([])
            interval = None
            if aligned_time.size == numeric.size and np.isfinite(aligned_time[longest[0]]) and np.isfinite(aligned_time[longest[1] - 1]):
                interval = (float(aligned_time[longest[0]]), float(aligned_time[longest[1] - 1]))
            findings.append(Finding(rule_id="SIGNAL-FLATLINE-002", outcome=Outcome.WARNING, severity=Severity.LOW,
                summary=f"{name} contains a sustained repeated-value interval",
                explanation="A run of at least 8 identical adjacent samples is a review candidate; valid held values and digital signals can produce plateaus.",
                evidence={**stats, "run_start_index": longest[0], "run_end_index": longest[1] - 1}, affected_interval=interval, source=source))
    if spike_indices:
        findings.append(Finding(rule_id="SIGNAL-SPIKE-001", outcome=Outcome.WARNING, severity=Severity.LOW,
            summary=f"{name} contains isolated spike candidates",
            explanation="A one-sample excursion that returns immediately is flagged using a robust first-difference scale; candidates require diagnostic context and are not called faults.",
            evidence={**stats, "sample_indices": spike_indices[:20]}, source=source))
    if not findings:
        findings.append(Finding(rule_id="SIGNAL-FINITE-001", outcome=Outcome.PASS, severity=Severity.INFO,
            summary=f"{name} has finite varying samples", explanation="No empty, missing, or constant-array condition was detected.", evidence=stats, source=source))
    return stats, findings


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    return [(int(start), int(end)) for start, end in zip(starts, ends, strict=True)]


def _constant_runs(values: np.ndarray) -> list[tuple[int, int]]:
    if values.size < 2:
        return []
    equal_adjacent = np.isfinite(values[:-1]) & np.isfinite(values[1:]) & (values[:-1] == values[1:])
    pair_runs = _runs(equal_adjacent)
    return [(start, end + 1) for start, end in pair_runs]


def _isolated_spikes(values: np.ndarray) -> list[int]:
    finite = np.isfinite(values)
    differences = np.diff(values)
    valid_diffs = differences[np.isfinite(values[:-1]) & np.isfinite(values[1:])]
    if valid_diffs.size < 5:
        return []
    center = float(np.median(valid_diffs))
    mad = float(np.median(np.abs(valid_diffs - center)))
    scale = 1.4826 * mad
    if scale <= np.finfo(float).eps:
        return []
    candidates: list[int] = []
    for index in range(1, values.size - 1):
        if not finite[index - 1:index + 2].all():
            continue
        excursion = values[index] - (values[index - 1] + values[index + 1]) / 2
        if abs(excursion) > 8 * scale and abs(differences[index - 1]) > 8 * scale and abs(differences[index]) > 8 * scale:
            candidates.append(index)
    candidate_set = set(candidates)
    return [index for index in candidates if index - 1 not in candidate_set and index + 1 not in candidate_set]
