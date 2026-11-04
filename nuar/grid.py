"""Map a point to NUAR's `grid` input (the 609-cell DMI climate grid field in
`NUAR-regneark!D5`, matching the workbook's own `GridTab`).

NUAR's own workbook never gives these 609 cells real coordinates — only a
non-georeferenced picture (`Klimagrid` sheet) with the IDs printed in their
correct relative positions. DMI itself, in its open-data site, publishes the
*same* 609-cell grid as real ETRS89 geometry, but under its own naming
(`DKN_10km_ETRS89`, cell IDs like "10km_605_65" = northing/10km, easting/10km)
— see `data/dmi_grid/SOURCE.md`.

The crosswalk between the two numbering schemes was inferred, not published
by DMI or SEGES: sort the 609 real cells by (easting ascending, northing
descending within each column) and number them 10001..10609 in that order.
This was checked three ways and matches on all of them:

- all 609 cells present, one-to-one, no gaps;
- the resulting 5 Georegion groups (`GridTab` column 2) land exactly on their
  named areas — region 1 "Thy" at lon 8.10-9.08 / lat 56.53-57.16, etc.;
- Bornholm (the only geographically isolated cluster, lon > 14.5) lands at
  IDs 10597-10609, matching the separate inset box in the workbook's own
  klimagrid picture;
- one column was checked cell-by-cell against IDs read off that picture:
  18 consecutive cells, 10014-10031, matched exactly.

Treat this as strongly evidenced, not officially confirmed by SEGES or DMI.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd

GEOJSON = Path(__file__).parents[1] / "data" / "dmi_grid" / "dkn_10km.geojson"
_cache: gpd.GeoDataFrame | None = None


def _cells() -> gpd.GeoDataFrame:
    global _cache
    if _cache is None:
        g = gpd.read_file(GEOJSON)
        g["northing_idx"] = g["cellId"].str.split("_").str[1].astype(int)
        g["easting_idx"] = g["cellId"].str.split("_").str[2].astype(int)
        order = g.sort_values(["easting_idx", "northing_idx"], ascending=[True, False])
        order = order.reset_index(drop=True)
        order["grid"] = 10001 + order.index
        _cache = order
    return _cache


def grid_for_points(points: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """points: a GeoDataFrame of point geometries (any CRS). Adds `grid`
    (NUAR's ID, int) and `dmi_cell_id` (DMI's own "10km_NNN_EE" label, for
    cross-checking). A point outside all 609 cells (outside Denmark) gets NaN.
    """
    cells = _cells()
    pts = points.to_crs(cells.crs)
    joined = gpd.sjoin(pts, cells[["geometry", "grid", "cellId"]].rename(
        columns={"cellId": "dmi_cell_id"}), how="left", predicate="within")
    return joined.drop(columns="index_right", errors="ignore").to_crs(points.crs)
