"""Pull retention % from the national UMR retention layer (geodata.fvm.dk, WFS)
and spatially join it onto a point dataset.
"""
from __future__ import annotations

import geopandas as gpd

WFS_URL = "https://geodata.fvm.dk/geoserver/ows"
TYPE_NAME = "Udledningsbaseret_mark_regulering:Kvaelstofretention_UMR_2027"


def fetch_retention(bbox=None):
    """The whole layer (~96,000 polygons) or just a bbox (minx,miny,maxx,maxy
    in EPSG:25832). The whole layer is a few tens of MB; cache it to disk if
    you'll run this more than once.
    """
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
              "typeName": TYPE_NAME, "outputFormat": "application/json",
              "srsName": "EPSG:25832"}
    if bbox:
        params["bbox"] = ",".join(map(str, bbox)) + ",EPSG:25832"
    gdf = gpd.read_file(WFS_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items()))
    return gdf.rename(columns={"RetTot": "retention_pct"})


def join_retention(points: gpd.GeoDataFrame, retention: gpd.GeoDataFrame | None = None):
    """points: a GeoDataFrame of point geometries (any CRS). Adds retention_pct.
    Points outside every polygon (coast edge effects, offshore, or exactly on a
    100 m cell boundary) get NaN.
    """
    if retention is None:
        minx, miny, maxx, maxy = points.to_crs(25832).total_bounds
        pad = 200  # metres; the layer is on a 100 m grid
        retention = fetch_retention((minx - pad, miny - pad, maxx + pad, maxy + pad))
    pts = points.to_crs(25832)
    joined = gpd.sjoin(pts, retention[["geometry", "retention_pct", "KystvandID"]],
                        how="left", predicate="within")
    return joined.drop(columns="index_right", errors="ignore").to_crs(points.crs)
