import numpy as np
import xarray as xr

from plasma_inspector.models import Outcome
from plasma_inspector.validation.equilibrium import inspect_equilibrium


def equilibrium_dataset(*, outside_axis: bool = False, repeated_r: bool = False) -> xr.Dataset:
    r = np.array([0.0, 1.0, 2.0])
    if repeated_r:
        r[1] = r[0]
    z = np.array([-1.0, 0.0, 1.0])
    boundary_r = np.array([[0.5, 0.5], [1.5, 1.5], [1.5, 1.5], [0.5, 0.5], [0.5, 0.5]])
    boundary_z = np.array([[-0.5, -0.5], [-0.5, -0.5], [0.5, 0.5], [0.5, 0.5], [-0.5, -0.5]])
    axis_r = np.array([1.0, 3.0 if outside_axis else 1.0])
    return xr.Dataset(
        data_vars={
            "psi": (("z", "major_radius", "time"), np.ones((3, 3, 2)), {"units": "Wb / rad"}),
            "magnetic_axis_r": (("time",), axis_r, {"units": "m"}),
            "magnetic_axis_z": (("time",), np.zeros(2), {"units": "m"}),
            "lcfs_r": (("n_boundary_coords", "time"), boundary_r, {"units": "m"}),
            "lcfs_z": (("n_boundary_coords", "time"), boundary_z, {"units": "m"}),
            "minor_radius": (("time",), np.array([0.5, 0.5]), {"units": "m", "description": "Half LCFS radial extent"}),
            "area": (("time",), np.array([1.0, 1.0]), {"units": "m ** 2"}),
            "elongation": (("time",), np.array([1.0, 1.0]), {"units": ""}),
        },
        coords={
            "major_radius": (("major_radius",), r, {"units": "m"}),
            "z": (("z",), z, {"units": "m"}),
            "time": (("time",), np.array([0.0, 0.1]), {"units": "s"}),
        },
    )


def test_equilibrium_consistency_checks_preserve_valid_source_geometry() -> None:
    findings = inspect_equilibrium(equilibrium_dataset(), source="fixture")
    by_rule = {finding.rule_id: finding for finding in findings}

    assert by_rule["EQ-GRID-SHAPE-001"].outcome == Outcome.PASS
    assert by_rule["EQ-TIME-SHAPE-001"].outcome == Outcome.PASS
    assert by_rule["EQ-AXIS-BOUNDS-001"].outcome == Outcome.PASS
    assert by_rule["EQ-LCFS-BOUNDS-001"].outcome == Outcome.PASS
    assert by_rule["EQ-LCFS-POLYGON-001"].outcome == Outcome.PASS
    assert by_rule["EQ-GEOMETRY-MINOR-RADIUS-001"].outcome == Outcome.PASS
    assert by_rule["EQ-AXIS-LCFS-001"].outcome == Outcome.PASS
    assert by_rule["EQ-GEOMETRY-AREA-001"].outcome == Outcome.PASS
    assert by_rule["EQ-GEOMETRY-ELONGATION-001"].outcome == Outcome.PASS


def test_equilibrium_checks_report_out_of_grid_axis_and_bad_coordinate_order() -> None:
    findings = inspect_equilibrium(equilibrium_dataset(outside_axis=True, repeated_r=True), source="fixture")
    by_rule = {finding.rule_id: finding for finding in findings}

    assert any(
        finding.rule_id == "EQ-COORD-ORDER-001"
        and finding.evidence["count"] == 3
        and finding.evidence["duplicate_count"] == 1
        and finding.outcome == Outcome.FAIL
        for finding in findings
    )
    assert by_rule["EQ-AXIS-BOUNDS-001"].outcome == Outcome.FAIL
    assert by_rule["EQ-AXIS-BOUNDS-001"].evidence["outside_frame_indices"] == [1]
