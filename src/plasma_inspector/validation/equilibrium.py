"""Source-aware structural checks for rectilinear equilibrium groups.

These checks validate the published arrays and coordinate relationships. They do
not classify an equilibrium as physically correct or infer an X-point convention.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from shapely.geometry import Point, Polygon

from plasma_inspector.models import Finding, Outcome, Severity

R_NAMES = {"major_radius", "r", "R"}
Z_NAMES = {"z", "vertical", "Z"}


def inspect_equilibrium(ds: Any, *, source: str) -> list[Finding]:
    findings: list[Finding] = []
    r_name = next((name for name in ("major_radius", "r", "R") if name in ds.coords), None)
    z_name = next((name for name in ("z", "vertical", "Z") if name in ds.coords), None)
    if r_name is None or z_name is None:
        return [Finding(
            rule_id="EQ-GRID-001", outcome=Outcome.NOT_EVALUATED, severity=Severity.INFO,
            summary="Equilibrium grid axes unavailable",
            explanation="Recognized radial and vertical coordinates are both required; array axes are not inferred.",
            evidence={"coordinates": list(ds.coords)}, source=source,
        )]

    r_coord, z_coord = ds.coords[r_name], ds.coords[z_name]
    r = np.asarray(r_coord.values, dtype=float).reshape(-1)
    z = np.asarray(z_coord.values, dtype=float).reshape(-1)
    findings.extend(_inspect_coordinate(r_name, r, r_coord.attrs.get("units"), source))
    findings.extend(_inspect_coordinate(z_name, z, z_coord.attrs.get("units"), source))
    if r_coord.ndim != 1 or z_coord.ndim != 1 or r_coord.dims != (r_name,) or z_coord.dims != (z_name,):
        findings.append(Finding(
            rule_id="EQ-GRID-TOPOLOGY-001", outcome=Outcome.NOT_EVALUATED, severity=Severity.INFO,
            summary="Non-rectilinear grid topology not evaluated",
            explanation="This validator currently supports only explicit one-dimensional rectilinear R/Z coordinates.",
            evidence={"r_dims": list(r_coord.dims), "z_dims": list(z_coord.dims)}, source=source,
        ))
        return findings

    psi = ds.data_vars.get("psi")
    if psi is None:
        findings.append(Finding(
            rule_id="EQ-GRID-001", outcome=Outcome.NOT_EVALUATED, severity=Severity.INFO,
            summary="Poloidal flux grid unavailable",
            explanation="No source variable named 'psi' is available; flux-axis mapping and finite-cell checks were skipped.",
            evidence={}, source=source,
        ))
    else:
        r_dim = next((dim for dim in psi.dims if dim in R_NAMES), None)
        z_dim = next((dim for dim in psi.dims if dim in Z_NAMES), None)
        if r_dim is None or z_dim is None or r_dim != r_name or z_dim != z_name:
            findings.append(Finding(
                rule_id="EQ-GRID-AXIS-001", outcome=Outcome.NOT_EVALUATED, severity=Severity.INFO,
                summary="Flux-map axes are ambiguous",
                explanation="The psi dimensions do not explicitly name the supplied R and Z coordinates; no transpose or shape-based mapping was attempted.",
                evidence={"dimensions": list(psi.dims), "r_coordinate": r_name, "z_coordinate": z_name}, source=source,
            ))
        elif psi.sizes[r_dim] != r.size or psi.sizes[z_dim] != z.size:
            findings.append(Finding(
                rule_id="EQ-GRID-SHAPE-001", outcome=Outcome.FAIL, severity=Severity.HIGH,
                summary="Flux-map dimensions disagree with coordinates",
                explanation="Named R/Z dimensions do not match their declared coordinate lengths.",
                evidence={"dimensions": list(psi.dims), "shape": list(psi.shape), "r_count": int(r.size), "z_count": int(z.size)}, source=source,
            ))
        else:
            findings.append(Finding(
                rule_id="EQ-GRID-SHAPE-001", outcome=Outcome.PASS, severity=Severity.INFO,
                summary="Flux-map dimensions match declared coordinates",
                explanation="Explicit R/Z dimension labels and coordinate lengths agree; this does not verify flux convention or physical validity.",
                evidence={"dimensions": list(psi.dims), "shape": list(psi.shape), "units": psi.attrs.get("units")}, source=source,
            ))
            if "time" in psi.dims:
                if "time" not in ds.coords or ds.coords["time"].size != psi.sizes["time"]:
                    findings.append(Finding(
                        rule_id="EQ-TIME-SHAPE-001", outcome=Outcome.FAIL, severity=Severity.HIGH,
                        summary="Flux frames do not map to the time coordinate",
                        explanation="The psi time dimension length differs from the group's declared time coordinate.",
                        evidence={"psi_time_count": int(psi.sizes["time"]), "time_count": int(ds.coords["time"].size) if "time" in ds.coords else None}, source=source,
                    ))
                else:
                    findings.append(Finding(
                        rule_id="EQ-TIME-SHAPE-001", outcome=Outcome.PASS, severity=Severity.INFO,
                        summary="Flux frames map to the time coordinate",
                        explanation="The named psi time dimension and source time coordinate have equal lengths.",
                        evidence={"frame_count": int(psi.sizes["time"])}, source=source,
                    ))
            values = np.asarray(psi.values, dtype=float)
            finite_by_frame = _finite_coverage(values, psi.dims, r_dim, z_dim)
            if finite_by_frame is not None:
                available = finite_by_frame > 0
                incomplete = available & (finite_by_frame < r.size * z.size)
                findings.append(Finding(
                    rule_id="EQ-FLUX-FINITE-001",
                    outcome=Outcome.WARNING if np.any(incomplete) else Outcome.PASS,
                    severity=Severity.MEDIUM if np.any(incomplete) else Severity.INFO,
                    summary="Some available flux frames contain nonfinite cells" if np.any(incomplete) else "Available flux frames have finite grid cells",
                    explanation="Only frames containing at least one finite cell are assessed; empty frames remain unavailable and are not treated as failed reconstructions.",
                    evidence={"available_frames": int(np.sum(available)), "empty_frames": int(np.sum(~available)), "incomplete_frames": np.flatnonzero(incomplete).tolist(), "grid_cells_per_frame": int(r.size * z.size)}, source=source,
                ))

    findings.extend(_inspect_axis(ds, r_name, z_name, r, z, source))
    findings.extend(_inspect_boundary(ds, r_name, z_name, r, z, source))
    return findings


def _inspect_coordinate(name: str, values: np.ndarray, units: str | None, source: str) -> list[Finding]:
    finite = np.isfinite(values)
    delta = np.diff(values) if np.all(finite) else np.asarray([], dtype=float)
    duplicate = int(np.sum(delta == 0))
    ordered = bool(delta.size and (np.all(delta > 0) or np.all(delta < 0)))
    evidence = {"count": int(values.size), "nonfinite_count": int(values.size - finite.sum()), "duplicate_count": duplicate, "strictly_monotonic": ordered, "units": units}
    out = [Finding(
        rule_id="EQ-COORD-FINITE-001", outcome=Outcome.PASS if values.size and np.all(finite) else Outcome.FAIL,
        severity=Severity.INFO if values.size and np.all(finite) else Severity.HIGH,
        summary=f"{name} coordinate is finite" if values.size and np.all(finite) else f"{name} coordinate is empty or nonfinite",
        explanation="Coordinate values are checked as stored; no sorting or repair is performed.", evidence=evidence, source=source,
    )]
    if values.size and np.all(finite):
        out.append(Finding(
            rule_id="EQ-COORD-ORDER-001", outcome=Outcome.PASS if ordered and duplicate == 0 else Outcome.FAIL,
            severity=Severity.INFO if ordered and duplicate == 0 else Severity.HIGH,
            summary=f"{name} coordinate is strictly monotonic" if ordered and duplicate == 0 else f"{name} coordinate is duplicated or nonmonotonic",
            explanation="Rectilinear grid validation requires a strictly monotonic source axis; descending source axes are accepted.", evidence=evidence, source=source,
        ))
    if not units:
        out.append(Finding(
            rule_id="EQ-COORD-UNITS-001", outcome=Outcome.WARNING, severity=Severity.LOW,
            summary=f"{name} coordinate has no declared units",
            explanation="The source coordinate is retained, but spatial measurements cannot be compared in physical units without a unit declaration.", evidence=evidence, source=source,
        ))
    return out


def _finite_coverage(values: np.ndarray, dims: tuple[str, ...], r_dim: str, z_dim: str) -> np.ndarray | None:
    if "time" not in dims:
        return None
    counts = np.isfinite(values).sum(axis=(dims.index(r_dim), dims.index(z_dim)))
    return np.asarray(counts).reshape(-1)


def _inspect_axis(ds: Any, r_name: str, z_name: str, r: np.ndarray, z: np.ndarray, source: str) -> list[Finding]:
    if "magnetic_axis_r" not in ds or "magnetic_axis_z" not in ds:
        return [Finding(
            rule_id="EQ-AXIS-001", outcome=Outcome.NOT_EVALUATED, severity=Severity.INFO,
            summary="Source magnetic-axis coordinates unavailable",
            explanation="Both source-provided magnetic_axis_r and magnetic_axis_z are required; the axis is not inferred from psi in this check.", evidence={}, source=source,
        )]
    axis_r, axis_z = np.asarray(ds["magnetic_axis_r"].values, dtype=float), np.asarray(ds["magnetic_axis_z"].values, dtype=float)
    if axis_r.shape != axis_z.shape:
        return [Finding(
            rule_id="EQ-AXIS-001", outcome=Outcome.FAIL, severity=Severity.HIGH,
            summary="Magnetic-axis coordinate shapes disagree",
            explanation="Source radial and vertical magnetic-axis arrays must have matching shapes.", evidence={"r_shape": list(axis_r.shape), "z_shape": list(axis_z.shape)}, source=source,
        )]
    finite = np.isfinite(axis_r) & np.isfinite(axis_z)
    inside = finite & (axis_r >= np.min(r)) & (axis_r <= np.max(r)) & (axis_z >= np.min(z)) & (axis_z <= np.max(z))
    outside = finite & ~inside
    return [Finding(
        rule_id="EQ-AXIS-BOUNDS-001", outcome=Outcome.FAIL if np.any(outside) else Outcome.PASS,
        severity=Severity.HIGH if np.any(outside) else Severity.INFO,
        summary="Finite magnetic-axis coordinates fall outside the grid" if np.any(outside) else "Finite magnetic-axis coordinates lie within the grid",
        explanation="Only finite source-provided axis pairs are checked against the declared coordinate bounds; unavailable frames are left unclassified.",
        evidence={"finite_frames": int(finite.sum()), "unavailable_frames": int(finite.size - finite.sum()), "outside_frame_indices": np.flatnonzero(outside).tolist(), "r_bounds": [float(np.min(r)), float(np.max(r))], "z_bounds": [float(np.min(z)), float(np.max(z))], "r_units": ds.coords[r_name].attrs.get("units"), "z_units": ds.coords[z_name].attrs.get("units")}, source=source,
    )]


def _inspect_boundary(ds: Any, r_name: str, z_name: str, r: np.ndarray, z: np.ndarray, source: str) -> list[Finding]:
    if "lcfs_r" not in ds or "lcfs_z" not in ds:
        return [Finding(
            rule_id="EQ-LCFS-001", outcome=Outcome.NOT_EVALUATED, severity=Severity.INFO,
            summary="Source LCFS coordinates unavailable",
            explanation="Both lcfs_r and lcfs_z are required; the boundary is not reconstructed from flux contours in this check.", evidence={}, source=source,
        )]
    br, bz = np.asarray(ds["lcfs_r"].values, dtype=float), np.asarray(ds["lcfs_z"].values, dtype=float)
    if br.shape != bz.shape or br.ndim != 2:
        return [Finding(
            rule_id="EQ-LCFS-SHAPE-001", outcome=Outcome.FAIL, severity=Severity.HIGH,
            summary="LCFS coordinate arrays have incompatible shapes",
            explanation="The source radial and vertical boundary arrays must be matching 2D point-by-time arrays.", evidence={"r_shape": list(br.shape), "z_shape": list(bz.shape)}, source=source,
        )]
    if br.shape[-1] != ds.sizes.get("time"):
        return [Finding(
            rule_id="EQ-LCFS-SHAPE-001", outcome=Outcome.FAIL, severity=Severity.HIGH,
            summary="LCFS boundary frames do not map to time",
            explanation="The final boundary dimension does not match the source time coordinate length.", evidence={"boundary_shape": list(br.shape), "time_count": ds.sizes.get("time")}, source=source,
        )]
    usable = np.isfinite(br) & np.isfinite(bz)
    finite_count = usable.sum(axis=0)
    available = finite_count >= 3
    outside = usable & ((br < np.min(r)) | (br > np.max(r)) | (bz < np.min(z)) | (bz > np.max(z)))
    outside_frames = np.any(outside, axis=0) & available
    findings = [Finding(
        rule_id="EQ-LCFS-BOUNDS-001", outcome=Outcome.FAIL if np.any(outside_frames) else Outcome.PASS,
        severity=Severity.HIGH if np.any(outside_frames) else Severity.INFO,
        summary="LCFS coordinates extend beyond the computational grid" if np.any(outside_frames) else "Available LCFS coordinates lie within the computational grid",
        explanation="Only frames with at least three paired finite boundary points are checked; source order and padding are preserved.",
        evidence={"available_frames": int(available.sum()), "unavailable_frames": int((~available).sum()), "outside_frame_indices": np.flatnonzero(outside_frames).tolist(), "r_grid_bounds": [float(np.min(r)), float(np.max(r))], "z_grid_bounds": [float(np.min(z)), float(np.max(z))], "r_units": ds[r_name].attrs.get("units"), "z_units": ds[z_name].attrs.get("units")}, source=source,
    )]
    invalid: list[int] = []
    polygons: dict[int, Polygon] = {}
    for frame in np.flatnonzero(available):
        points = np.column_stack((br[usable[:, frame], frame], bz[usable[:, frame], frame]))
        polygon = Polygon(points)
        if len(np.unique(points, axis=0)) < 3 or not polygon.is_valid or polygon.area == 0:
            invalid.append(int(frame))
        else:
            polygons[int(frame)] = polygon
    findings.append(Finding(
        rule_id="EQ-LCFS-POLYGON-001", outcome=Outcome.WARNING if invalid else Outcome.PASS,
        severity=Severity.MEDIUM if invalid else Severity.INFO,
        summary="Some source LCFS frames do not form valid polygons" if invalid else "Available source LCFS frames form valid polygons",
        explanation="Finite source boundary points are passed in source order to a planar polygon validity check; no contour is closed, reordered, or repaired by this audit.",
        evidence={"checked_frames": np.flatnonzero(available).tolist(), "invalid_frame_indices": invalid}, source=source,
    ))
    if "magnetic_axis_r" in ds and "magnetic_axis_z" in ds:
        axis_r = np.asarray(ds["magnetic_axis_r"].values, dtype=float).reshape(-1)
        axis_z = np.asarray(ds["magnetic_axis_z"].values, dtype=float).reshape(-1)
        if axis_r.size == br.shape[-1] and axis_z.size == br.shape[-1]:
            checked = [i for i in polygons if np.isfinite(axis_r[i]) and np.isfinite(axis_z[i])]
            outside_axis = [i for i in checked if not polygons[i].covers(Point(axis_r[i], axis_z[i]))]
            findings.append(Finding(
                rule_id="EQ-AXIS-LCFS-001", outcome=Outcome.WARNING if outside_axis else Outcome.PASS,
                severity=Severity.MEDIUM if outside_axis else Severity.INFO,
                summary="Source magnetic axis lies outside some LCFS polygons" if outside_axis else "Source magnetic axis lies inside available LCFS polygons",
                explanation="Finite source-provided axis coordinates are tested against valid source-order LCFS polygons; missing frames and invalid polygons are excluded.",
                evidence={"checked_frames": checked, "outside_frame_indices": outside_axis}, source=source,
            ))
    if "minor_radius" in ds:
        minor = np.asarray(ds["minor_radius"].values, dtype=float).reshape(-1)
        if minor.size == br.shape[-1]:
            discrepancies: list[tuple[int, float]] = []
            for frame in np.flatnonzero(available & np.isfinite(minor)):
                width_radius = (float(np.max(br[usable[:, frame], frame])) - float(np.min(br[usable[:, frame], frame]))) / 2
                discrepancies.append((int(frame), abs(width_radius - float(minor[frame]))))
            if discrepancies:
                # Source variable description defines minor_radius from LCFS radial extent.
                tolerance = max(1e-4, float(np.max(np.abs(np.diff(r)))) * 0.1)
                discrepant = [(i, d) for i, d in discrepancies if d > tolerance]
                findings.append(Finding(
                    rule_id="EQ-GEOMETRY-MINOR-RADIUS-001", outcome=Outcome.WARNING if discrepant else Outcome.PASS,
                    severity=Severity.MEDIUM if discrepant else Severity.INFO,
                    summary="Reported minor radius differs from LCFS radial extent" if discrepant else "Reported minor radius agrees with LCFS radial extent",
                    explanation="The FAIR-MAST source description defines minor_radius as half the LCFS R span; comparison uses a tolerance of 10% of one radial grid interval to allow for boundary-point discretization, with a 0.1 mm floor.",
                    evidence={"checked_frames": len(discrepancies), "discrepant_frames": [i for i, _ in discrepant], "maximum_absolute_difference_m": max(d for _, d in discrepancies), "tolerance_m": tolerance, "source_description": ds["minor_radius"].attrs.get("description")}, source=source,
                ))
    for name, derive, tolerance_fraction in (
        ("area", lambda points, polygon: float(polygon.area), 0.01),
        ("elongation", lambda points, polygon: float(np.ptp(points[:, 1]) / np.ptp(points[:, 0])) if np.ptp(points[:, 0]) > 0 else float("nan"), 0.01),
    ):
        if name not in ds:
            continue
        reported = np.asarray(ds[name].values, dtype=float).reshape(-1)
        geometry_discrepancies: list[tuple[int, float, float]] = []
        for frame, polygon in polygons.items():
            if frame >= reported.size or not np.isfinite(reported[frame]):
                continue
            points = np.column_stack((br[usable[:, frame], frame], bz[usable[:, frame], frame]))
            derived = derive(points, polygon)
            if np.isfinite(derived):
                absolute = abs(derived - float(reported[frame]))
                relative = absolute / max(abs(float(reported[frame])), 1e-12)
                geometry_discrepancies.append((frame, absolute, relative))
        if geometry_discrepancies:
            discrepant = [(frame, absolute, relative) for frame, absolute, relative in geometry_discrepancies if relative > tolerance_fraction]
            findings.append(Finding(
                rule_id=f"EQ-GEOMETRY-{name.upper()}-001", outcome=Outcome.WARNING if discrepant else Outcome.PASS,
                severity=Severity.MEDIUM if discrepant else Severity.INFO,
                summary=f"Reported {name} differs from LCFS-derived geometry" if discrepant else f"Reported {name} agrees with LCFS-derived geometry",
                explanation=f"Derived from the source LCFS polygon; relative tolerance is {tolerance_fraction:.0%}. This is a consistency check, not an independent reconstruction of the boundary.",
                evidence={"checked_frames": len(geometry_discrepancies), "discrepant_frame_indices": [i for i, _, _ in discrepant], "maximum_absolute_difference": max(d for _, d, _ in geometry_discrepancies), "maximum_relative_difference": max(d for _, _, d in geometry_discrepancies), "relative_tolerance": tolerance_fraction, "source_description": ds[name].attrs.get("description")}, source=source,
            ))
    return findings
