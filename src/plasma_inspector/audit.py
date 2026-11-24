from __future__ import annotations

from datetime import UTC, datetime

from plasma_inspector.adapters.fairmast import FairMastAdapter
from plasma_inspector.models import AuditReport, Finding, Outcome, Provenance, Severity
from plasma_inspector.validation.equilibrium import inspect_equilibrium
from plasma_inspector.validation.signal import inspect_signal
from plasma_inspector.validation.time_axis import inspect_time_axis


def audit_shot(shot_id: int, level: int = 2, group: str = "summary") -> AuditReport:
    adapter = FairMastAdapter(level)
    metadata = adapter.get_shot_metadata(shot_id)
    provenance_data = adapter.provenance(shot_id)
    ds = adapter.load_group(shot_id, group)
    findings: list[Finding] = []
    time = ds.coords.get("time")
    if time is not None:
        _, time_findings = inspect_time_axis(time.values, source=adapter.source_id)
        findings.extend(time_findings)
    else:
        findings.append(Finding(
            rule_id="TIME-STRUCTURE-001", outcome=Outcome.NOT_EVALUATED,
            severity=Severity.INFO, summary="No shared time coordinate",
            explanation=f"Group '{group}' does not expose a 'time' coordinate.",
            source=adapter.source_id,
        ))
    for name, variable in ds.data_vars.items():
        signal_time = time.values if time is not None and variable.dims == ("time",) else None
        _, signal_findings = inspect_signal(
            variable.values, name=str(name), units=variable.attrs.get("units"),
            source=adapter.source_id, time=signal_time,
        )
        findings.extend(signal_findings)
    if group == "equilibrium":
        findings.extend(inspect_equilibrium(ds, source=adapter.source_id))
    else:
        findings.append(Finding(
            rule_id="EQ-GRID-001", outcome=Outcome.NOT_EVALUATED, severity=Severity.INFO,
            summary="Equilibrium grid not inspected",
            explanation="Run this audit on the equilibrium group; no equilibrium claims are inferred from the selected signal group.",
            source=adapter.source_id,
        ))

    ingest_commit = None
    for attr in ds.attrs.values():
        if isinstance(attr, str) and "github.com/ukaea/fair-mast-ingestion/tree/" in attr:
            ingest_commit = attr.rsplit("/", 1)[-1].split()[0]
    provenance_data["ingestion_commit"] = ingest_commit
    provenance_data["retrieved_at"] = datetime.now(UTC)
    provenance_data["quality_status"] = metadata.get("quality")
    not_evaluated = sum(f.outcome == Outcome.NOT_EVALUATED for f in findings)
    return AuditReport(
        shot_id=shot_id, dataset=adapter.source_id, findings=findings,
        rules_evaluated=len(findings) - not_evaluated, rules_not_evaluated=not_evaluated,
        limitations=[
            "Statistical anomalies are screening candidates, not evidence of instrument failure.",
            "Only the selected Zarr group was loaded; other diagnostics were not audited.",
            "FAIR-MAST Level 2 includes source-specific cropping, interpolation and calibration; consult group provenance.",
            "Equilibrium checks validate source coordinate and geometry consistency; they do not certify EFIT physical correctness.",
        ],
        provenance=Provenance.model_validate(provenance_data),
    )
