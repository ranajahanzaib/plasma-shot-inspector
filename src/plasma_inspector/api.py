from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from plasma_inspector.adapters.fairmast import FairMastAdapter
from plasma_inspector.audit import audit_shot

DB_PATH = Path(os.environ.get("PLASMA_INSPECTOR_DB", "data/inspector.sqlite"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Plasma Shot Inspector API", version="1.0.0", description="Read-only FAIR-MAST catalog and transparent shot audits.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["GET", "POST"], allow_headers=["*"])


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS audits (id TEXT PRIMARY KEY, shot_id INTEGER, level INTEGER, status TEXT, report TEXT, error TEXT, created_at TEXT)")
    return con


def _run_audit(audit_id: str, shot_id: int, level: int, group: str) -> None:
    con = _db()
    con.execute("UPDATE audits SET status='running' WHERE id=?", (audit_id,))
    con.commit()
    try:
        report = audit_shot(shot_id, level, group)
        con.execute("UPDATE audits SET status='completed', report=? WHERE id=?", (report.model_dump_json(), audit_id))
    except Exception as exc:  # noqa: BLE001 — persist unexpected background-job failures.
        con.execute("UPDATE audits SET status='failed', error=? WHERE id=?", (str(exc), audit_id))
    con.commit()
    con.close()


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "plasma-shot-inspector-api"}


@app.get("/api/v1/datasets")
def datasets() -> list[dict[str, str]]:
    return [{"id": f"fair-mast-l{i}", "label": f"FAIR-MAST Level {i}", "status": "available", "description": "Remote public catalog; fetch is selective."} for i in (1, 2)]


@app.get("/api/v1/machines")
def machines() -> list[dict[str, str]]:
    return [{"id": "mast", "label": "MAST", "status": "operational", "source": "FAIR-MAST"}]


@app.get("/api/v1/shots")
def shots(level: int = Query(2, ge=1, le=2), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), q: str | None = None) -> dict[str, Any]:
    try:
        rows = FairMastAdapter(level).list_shots(limit, offset, q)
        return {"items": rows, "limit": limit, "offset": offset, "source": f"fair-mast-l{level}"}
    except Exception as exc:
        raise HTTPException(502, detail={"code": "catalog_unavailable", "message": str(exc)}) from exc


@app.get("/api/v1/shots/{shot_id}")
def shot(shot_id: int, level: int = Query(2, ge=1, le=2)) -> dict[str, Any]:
    adapter = FairMastAdapter(level)
    try:
        return {"metadata": adapter.get_shot_metadata(shot_id), "provenance": adapter.provenance(shot_id)}
    except KeyError as exc:
        raise HTTPException(404, detail={"code": "shot_not_found", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(502, detail={"code": "catalog_unavailable", "message": str(exc)}) from exc


@app.get("/api/v1/shots/{shot_id}/signals")
def signals(shot_id: int, level: int = Query(2, ge=1, le=2)) -> list[dict[str, Any]]:
    try:
        return FairMastAdapter(level).list_signals(shot_id)
    except KeyError as exc:
        raise HTTPException(404, detail={"code": "shot_not_found", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(502, detail={"code": "source_unavailable", "message": str(exc)}) from exc


@app.get("/api/v1/shots/{shot_id}/groups/{group}")
def group_summary(shot_id: int, group: str, level: int = Query(2, ge=1, le=2)) -> dict[str, Any]:
    try:
        ds = FairMastAdapter(level).load_group(shot_id, group)
        return {"shot_id": shot_id, "source": f"fair-mast-l{level}", "group": group,
          "dimensions": dict(ds.sizes), "coordinates": list(ds.coords),
          "variables": [{"name": name, "shape": list(var.shape), "dimensions": list(var.dims), "units": var.attrs.get("units"), "dtype": str(var.dtype)} for name, var in ds.data_vars.items()],
          "provenance": {"ingested_at": ds.attrs.get("ingested_at"), "commit_url": ds.attrs.get("commit_url"), "license_name": ds.attrs.get("license_name")}}
    except KeyError as exc:
        raise HTTPException(404, detail={"code": "shot_not_found", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(502, detail={"code": "group_unavailable", "message": str(exc)}) from exc


@app.get("/api/v1/shots/{shot_id}/samples/{signal_name}")
def signal_samples(shot_id: int, signal_name: str, group: str = "summary", level: int = Query(2, ge=1, le=2), limit: int = Query(1200, ge=10, le=5000)) -> dict[str, Any]:
    try:
        ds = FairMastAdapter(level).load_group(shot_id, group)
        if signal_name not in ds.data_vars:
            raise HTTPException(404, detail={"code": "signal_not_found", "message": f"{signal_name} is not a variable in group {group}."})
        var = ds[signal_name]
        values = var.values
        if values.ndim != 1:
            raise HTTPException(422, detail={"code": "multidimensional_signal", "message": "Use the diagnostic-specific profile view for multidimensional data."})
        count = values.size
        step = max(1, (count + limit - 1) // limit)
        sampled = values[::step]
        time_values = ds.coords["time"].values[::step] if "time" in ds.coords and ds.coords["time"].size == count else None
        return {"shot_id": shot_id, "group": group, "name": signal_name, "units": var.attrs.get("units"),
          "dimensions": list(var.dims), "display_only": step > 1, "display_stride": step,
          "time": time_values.tolist() if time_values is not None else None, "values": sampled.tolist()}
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(404, detail={"code": "shot_not_found", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(502, detail={"code": "signal_unavailable", "message": str(exc)}) from exc


@app.get("/api/v1/shots/{shot_id}/equilibrium/frame")
def equilibrium_frame(shot_id: int, index: int | None = Query(None, ge=0), level: int = Query(2, ge=1, le=2)) -> dict[str, Any]:
    """Return one source-order flux frame only when grid axes are explicitly named."""
    import numpy as np

    try:
        ds = FairMastAdapter(level).load_group(shot_id, "equilibrium")
        if "psi" not in ds.data_vars:
            raise HTTPException(404, detail={"code": "flux_map_unavailable", "message": "No source variable named psi is present."})
        var = ds["psi"]
        r_dim = next((name for name in ("major_radius", "r", "R") if name in var.dims and name in ds.coords), None)
        z_dim = next((name for name in ("z", "vertical", "Z") if name in var.dims and name in ds.coords), None)
        if r_dim is None or z_dim is None or "time" not in var.dims or "time" not in ds.coords:
            raise HTTPException(422, detail={"code": "ambiguous_flux_axes", "message": "psi must declare time, radial and vertical dimensions with matching coordinates."})
        count = int(ds.sizes["time"])
        frame_selection = "requested source-order index"
        if index is None:
            coverage = np.isfinite(var.values).sum(axis=(var.get_axis_num(z_dim), var.get_axis_num(r_dim)))
            index = int(np.argmax(coverage)) if coverage.size and np.max(coverage) else 0
            frame_selection = "frame with the most finite psi cells; no measurements altered"
        if index >= count:
            raise HTTPException(422, detail={"code": "frame_out_of_range", "message": f"Frame index must be less than {count}."})
        frame = var.isel(time=index).transpose(z_dim, r_dim)
        z = np.asarray(ds.coords[z_dim].values, dtype=float)
        r = np.asarray(ds.coords[r_dim].values, dtype=float)
        values = np.asarray(frame.values, dtype=float)
        if values.shape != (z.size, r.size):
            raise HTTPException(422, detail={"code": "coordinate_shape_mismatch", "message": "Named psi dimensions do not match coordinate array lengths."})

        def paired(names: tuple[str, ...]) -> list[float] | None:
            if any(name not in ds.data_vars for name in names):
                return None
            first, second = (ds[name] for name in names)
            if "time" not in first.dims or "time" not in second.dims:
                return None
            a, b = float(first.isel(time=index).values), float(second.isel(time=index).values)
            return [a, b]

        return {
            "shot_id": shot_id, "dataset": f"fair-mast-l{level}", "group": "equilibrium",
            "frame_index": index, "frame_count": count, "frame_selection": frame_selection,
            "frame_time": float(ds.coords["time"].isel(time=index).values),
            "r": r.tolist(), "z": z.tolist(),
            "psi": [[float(v) if np.isfinite(v) else None for v in row] for row in values],
            "psi_units": var.attrs.get("units"), "r_units": ds.coords[r_dim].attrs.get("units"),
            "z_units": ds.coords[z_dim].attrs.get("units"),
            "magnetic_axis": paired(("magnetic_axis_r", "magnetic_axis_z")),
            "provenance": {"ingested_at": ds.attrs.get("ingested_at"), "commit_url": ds.attrs.get("commit_url"), "license_name": ds.attrs.get("license_name")},
        }
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(404, detail={"code": "shot_not_found", "message": str(exc)}) from exc
    except Exception as exc:
        raise HTTPException(502, detail={"code": "equilibrium_unavailable", "message": str(exc)}) from exc


@app.post("/api/v1/audits", status_code=202)
def create_audit(background: BackgroundTasks, shot_id: int, level: int = Query(2, ge=1, le=2), group: str = "summary") -> dict[str, str]:
    if group not in {"summary", "equilibrium", "magnetics", "thomson_scattering"}:
        raise HTTPException(422, detail={"code": "unsupported_group", "message": "Select a documented FAIR-MAST group."})
    audit_id = str(uuid4())
    con = _db()
    con.execute("INSERT INTO audits(id, shot_id, level, status, created_at) VALUES(?,?,?,?,?)", (audit_id, shot_id, level, "queued", datetime.now(UTC).isoformat()))
    con.commit(); con.close()
    background.add_task(_run_audit, audit_id, shot_id, level, group)
    return {"id": audit_id, "status": "queued"}


@app.get("/api/v1/audits")
def list_audits(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    con = _db(); rows = con.execute("SELECT id, shot_id, level, status, created_at FROM audits ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall(); con.close()
    return [dict(zip(("id", "shot_id", "level", "status", "created_at"), row)) for row in rows]


@app.get("/api/v1/audits/{audit_id}")
def get_audit(audit_id: str) -> dict[str, Any]:
    con = _db(); row = con.execute("SELECT id, shot_id, level, status, report, error, created_at FROM audits WHERE id=?", (audit_id,)).fetchone(); con.close()
    if not row: raise HTTPException(404, detail={"code": "audit_not_found", "message": "Audit does not exist."})
    data = dict(zip(("id", "shot_id", "level", "status", "report", "error", "created_at"), row))
    if data["report"]: data["report"] = json.loads(data["report"])
    return {str(key): value for key, value in data.items()}


@app.get("/api/v1/rules")
def rules() -> list[dict[str, str]]:
    return [
      {"id": "TIME-EMPTY-001", "version": "1.0.0", "purpose": "Detect empty time coordinates"},
      {"id": "TIME-FINITE-001", "version": "1.0.0", "purpose": "Detect nonfinite time samples"},
      {"id": "TIME-DUPLICATE-001", "version": "1.0.0", "purpose": "Detect repeated adjacent timestamps"},
      {"id": "TIME-ORDER-001", "version": "1.0.0", "purpose": "Detect reversed or decreasing adjacent timestamps"},
      {"id": "TIME-GAP-001", "version": "1.0.0", "purpose": "Report large intervals as sampling review candidates"},
      {"id": "TIME-STRUCTURE-001", "version": "1.0.0", "purpose": "Report finite, ordered timestamp structure"},
      {"id": "SIGNAL-EMPTY-001", "version": "1.0.0", "purpose": "Detect empty source arrays"},
      {"id": "SIGNAL-FINITE-001", "version": "1.0.0", "purpose": "Measure source missingness without imputation"},
      {"id": "SIGNAL-FLAT-001", "version": "1.0.0", "purpose": "Flag globally constant signals as inspection candidates"},
      {"id": "SIGNAL-FLATLINE-002", "version": "1.0.0", "purpose": "Flag sustained identical adjacent values as candidates"},
      {"id": "SIGNAL-SPIKE-001", "version": "1.0.0", "purpose": "Flag isolated one-sample excursions as candidates"},
      {"id": "EQ-GRID-001", "version": "1.0.0", "purpose": "Report whether a supported equilibrium flux grid is available"},
      {"id": "EQ-COORD-FINITE-001", "version": "1.0.0", "purpose": "Validate R/Z coordinate finiteness"},
      {"id": "EQ-COORD-ORDER-001", "version": "1.0.0", "purpose": "Validate strict R/Z coordinate monotonicity"},
      {"id": "EQ-COORD-UNITS-001", "version": "1.0.0", "purpose": "Report absent coordinate unit declarations"},
      {"id": "EQ-GRID-TOPOLOGY-001", "version": "1.0.0", "purpose": "Report unsupported nonrectilinear grid topology"},
      {"id": "EQ-GRID-AXIS-001", "version": "1.0.0", "purpose": "Require named R/Z dimensions instead of inferring axis order"},
      {"id": "EQ-GRID-SHAPE-001", "version": "1.0.0", "purpose": "Compare named flux-grid dimensions to coordinate lengths"},
      {"id": "EQ-TIME-SHAPE-001", "version": "1.0.0", "purpose": "Validate flux frame and time coordinate correspondence"},
      {"id": "EQ-FLUX-FINITE-001", "version": "1.0.0", "purpose": "Measure finite-cell coverage for available flux frames"},
      {"id": "EQ-AXIS-001", "version": "1.0.0", "purpose": "Report unavailable source magnetic-axis coordinates"},
      {"id": "EQ-AXIS-BOUNDS-001", "version": "1.0.0", "purpose": "Check finite source axis positions against grid bounds"},
      {"id": "EQ-SPATIAL-001", "version": "1.0.0", "purpose": "Report why spatial bounds checks could not run"},
      {"id": "EQ-LCFS-001", "version": "1.0.0", "purpose": "Report unavailable source LCFS coordinates"},
      {"id": "EQ-LCFS-SHAPE-001", "version": "1.0.0", "purpose": "Validate source LCFS array shape and frame mapping"},
      {"id": "EQ-LCFS-BOUNDS-001", "version": "1.0.0", "purpose": "Check available LCFS points against grid bounds"},
      {"id": "EQ-LCFS-POLYGON-001", "version": "1.0.0", "purpose": "Check source-order LCFS polygon validity without repair"},
      {"id": "EQ-AXIS-LCFS-001", "version": "1.0.0", "purpose": "Check source magnetic-axis containment in valid LCFS polygons"},
      {"id": "EQ-GEOMETRY-MINOR-RADIUS-001", "version": "1.0.0", "purpose": "Compare source minor radius with LCFS radial extent"},
      {"id": "EQ-GEOMETRY-AREA-001", "version": "1.0.0", "purpose": "Compare source area with LCFS polygon area"},
      {"id": "EQ-GEOMETRY-ELONGATION-001", "version": "1.0.0", "purpose": "Compare source elongation with LCFS extent ratio"},
    ]
