"""FAIR-MAST metadata and lazy shot adapter.

Metadata filenames and the public HTTPS endpoint follow the FAIR-MAST quickstart.
Remote Zarr groups remain lazy until a caller explicitly reads a variable.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import polars as pl
import xarray as xr


class FairMastAdapter:
    endpoint = "https://s3.echo.stfc.ac.uk/mast"
    metadata_endpoint = f"{endpoint}/fairmast-meta"

    def __init__(self, level: int = 2) -> None:
        if level not in (1, 2):
            raise ValueError("FAIR-MAST level must be 1 or 2")
        self.level = level
        self.source_id = f"fair-mast-l{level}"

    @property
    def _shots_url(self) -> str:
        return f"{self.metadata_endpoint}/l{self.level}_shots.parquet"

    @property
    def _signals_url(self) -> str:
        return f"{self.metadata_endpoint}/l{self.level}_signals"

    def _shots(self) -> pl.DataFrame:
        return _read_shots(self.level)

    def list_shots(self, limit: int = 50, offset: int = 0, query: str | None = None) -> list[dict[str, Any]]:
        frame = self._shots()
        if query:
            columns = [c for c, dtype in frame.schema.items() if dtype == pl.String]
            expressions = [pl.col(c).str.contains(query, literal=True, strict=False) for c in columns]
            if query.isdigit() and "shot_id" in frame.columns:
                expressions.append(pl.col("shot_id") == int(query))
            if expressions:
                frame = frame.filter(pl.any_horizontal(expressions))
        return frame.slice(offset, limit).to_dicts()

    def get_shot_metadata(self, shot_id: int) -> dict[str, Any]:
        frame = self._shots().filter(pl.col("shot_id") == shot_id)
        if frame.is_empty():
            raise KeyError(f"Shot {shot_id} is not in FAIR-MAST level {self.level} catalog")
        return frame.row(0, named=True)

    def list_signals(self, shot_id: int) -> list[dict[str, Any]]:
        self.get_shot_metadata(shot_id)
        url = f"{self._signals_url}/signals_{shot_id}.parquet"
        return pl.read_parquet(url).to_dicts()

    def load_group(self, shot_id: int, group: str) -> xr.Dataset:
        if not group or "/" in group or group in {".", ".."}:
            raise ValueError("Group must be a single Zarr group name")
        self.get_shot_metadata(shot_id)
        url = f"{self.endpoint}/level{self.level}/shots/{shot_id}.zarr"
        return xr.open_zarr(url, group=group, chunks="auto")

    def provenance(self, shot_id: int) -> dict[str, Any]:
        return {
            "source": self.source_id,
            "source_url": f"{self.endpoint}/level{self.level}/shots/{shot_id}.zarr",
            "revision": "mutable FAIR-MAST release; inspect group ingested_at/commit_url attributes",
            "retrieved_at": None,
        }


class FairMastLevel1Adapter(FairMastAdapter):
    def __init__(self) -> None:
        super().__init__(1)


class FairMastLevel2Adapter(FairMastAdapter):
    def __init__(self) -> None:
        super().__init__(2)


@lru_cache(maxsize=2)
def _read_shots(level: int) -> pl.DataFrame:
    return pl.read_parquet(f"{FairMastAdapter.metadata_endpoint}/l{level}_shots.parquet")
