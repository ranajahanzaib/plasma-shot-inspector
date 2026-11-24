from __future__ import annotations

import numpy as np

from plasma_inspector.models import Finding, Outcome, Severity, TimeAxisResult


def inspect_time_axis(
    values: np.ndarray, *, source: str | None = None, gap_factor: float = 5.0,
) -> tuple[TimeAxisResult, list[Finding]]:
    """Inspect timestamps in source order; report large gaps as review candidates."""
    time = np.asarray(values, dtype=float).reshape(-1)
    finite = time[np.isfinite(time)]
    delta = np.diff(time)
    adjacent_finite = np.isfinite(time[:-1]) & np.isfinite(time[1:])
    adjacent_delta = delta[adjacent_finite]
    pair_indices = np.flatnonzero(adjacent_finite)
    positive = adjacent_delta[adjacent_delta > 0]
    median = float(np.median(positive)) if positive.size else None
    irregular = None
    if median is not None:
        irregular = float(np.mean(np.abs(positive - median) > max(abs(median) * 0.05, 1e-12)))
    duplicate_count = int(np.sum(adjacent_delta == 0))
    nonmonotonic_count = int(np.sum(adjacent_delta < 0))
    result = TimeAxisResult(
        sample_count=int(time.size), finite_count=int(finite.size), duplicate_count=duplicate_count,
        nonmonotonic_count=nonmonotonic_count, median_interval=median,
        irregularity_fraction=irregular, negative_time_count=int(np.sum(finite < 0)),
    )
    findings: list[Finding] = []
    if time.size == 0:
        findings.append(Finding(rule_id="TIME-EMPTY-001", outcome=Outcome.FAIL, severity=Severity.HIGH,
            summary="Time axis is empty", explanation="The source coordinate contains no timestamp samples.", evidence={"sample_count": 0}, source=source))
    if finite.size != time.size:
        findings.append(Finding(rule_id="TIME-FINITE-001", outcome=Outcome.FAIL, severity=Severity.HIGH,
            summary="Nonfinite timestamps", explanation="Some timestamp samples are NaN or infinite.",
            evidence={"invalid_count": int(time.size - finite.size)}, source=source))
    if duplicate_count:
        findings.append(Finding(rule_id="TIME-DUPLICATE-001", outcome=Outcome.FAIL, severity=Severity.MEDIUM,
            summary="Duplicate timestamps", explanation="Adjacent finite timestamps repeat; source order is preserved.",
            evidence={"count": duplicate_count}, source=source))
    if nonmonotonic_count:
        transitions = [
            {"left_index": int(pair_indices[i]), "right_index": int(pair_indices[i] + 1),
             "left_time": float(time[pair_indices[i]]), "right_time": float(time[pair_indices[i] + 1])}
            for i in np.flatnonzero(adjacent_delta < 0)[:20]
        ]
        reversed_axis = bool(adjacent_delta.size and np.all(adjacent_delta < 0))
        findings.append(Finding(rule_id="TIME-ORDER-001", outcome=Outcome.FAIL, severity=Severity.HIGH,
            summary="Time axis is reversed" if reversed_axis else "Nonmonotonic timestamps",
            explanation="Adjacent finite timestamps decrease in source order; no automatic sorting was applied.",
            evidence={"count": nonmonotonic_count, "transitions": transitions}, source=source))
    if median is not None and median > 0:
        gap_local_indices = np.flatnonzero(adjacent_finite & (delta > gap_factor * median))
        if gap_local_indices.size:
            gaps = [{"left_index": int(i), "right_index": int(i + 1), "start": float(time[i]),
                     "end": float(time[i + 1]), "duration": float(delta[i])} for i in gap_local_indices[:20]]
            findings.append(Finding(rule_id="TIME-GAP-001", outcome=Outcome.WARNING, severity=Severity.LOW,
                summary="Large timestamp gaps need review",
                explanation=f"Intervals longer than {gap_factor:g} times the median positive interval are listed as candidates; sparse or irregular diagnostics may make them expected.",
                evidence={"gap_factor": gap_factor, "median_interval": median, "count": int(gap_local_indices.size), "gaps": gaps}, source=source))
    if not findings:
        findings.append(Finding(rule_id="TIME-STRUCTURE-001", outcome=Outcome.PASS, severity=Severity.INFO,
            summary="Timestamp structure is finite and ordered", explanation="No nonfinite, duplicate, or decreasing adjacent timestamps were found.",
            evidence=result.model_dump(), source=source))
    return result, findings
