"""Run NUAR for a table of points: python -m nuar run points.csv -o result.csv"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .excel import OUTPUTS, ROW_CELLS, SITE_CELLS, SLOTS, run_excel
from .model import compute, solve_mineral_n
from .tables import SUPPORTED_VERSION, load

DEFAULTS = {"year": 2027, "n_level_scope": "Høstår", "manure_type": "Svinegylle",
            "irrigated": False, "lowland": None}
REQUIRED = ("jb", "c_horizon", "crop", "cover",
            "prev_crop", "prev_cover", "prev2_crop", "prev2_cover")
# grid and retention_pct are required too, but --fetch-grid/--fetch-retention
# can fill them in, so they are checked separately, after those steps run.
FLAGS = ("irrigated", "early_sowing", "intermediate_crop", "precision")
TRUE = {"1", "true", "ja", "yes", "y"}


def read_points(path):
    path = Path(path)
    if path.suffix.lower() in (".csv", ".txt"):
        df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig", dtype=object)
        if {"x", "y"} <= set(df.columns):
            import geopandas as gpd
            crs = "EPSG:25832" if df["x"].astype(float).max() > 1000 else "EPSG:4326"
            df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["x"], df["y"]), crs=crs)
        return df
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    import geopandas as gpd
    return gpd.read_file(path)


def write_points(df, path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        df.drop(columns="geometry", errors="ignore").to_csv(path, index=False, encoding="utf-8-sig")
    elif path.suffix.lower() == ".parquet":
        df.to_parquet(path)
    else:
        df.to_file(path)


def _clean(v, key):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA or v == "":
        return None
    if key in FLAGS:
        return str(v).strip().casefold() in TRUE
    if key in ("catch_crop_date", "c_horizon", "lowland", "manure_type", "n_level_scope"):
        return str(v)
    f = float(v)
    return int(f) if f.is_integer() else f


def split_rows(df):
    keys_site, keys_row = list(SITE_CELLS), list(ROW_CELLS)
    for rec in df.to_dict("records"):
        site = {k: _clean(rec.get(k), k) for k in keys_site}
        site = {k: (DEFAULTS.get(k) if v is None else v) for k, v in site.items()}
        yield site, {k: _clean(rec.get(k), k) for k in keys_row}


def _excel_batches(pairs):
    """Rows that share a site go in one recalculation, at most five at a time."""
    groups = {}
    for i, (site, row) in enumerate(pairs):
        groups.setdefault(tuple(sorted(site.items(), key=lambda x: x[0])), []).append((i, site, row))
    for members in groups.values():
        for j in range(0, len(members), SLOTS):
            yield members[j:j + SLOTS]


def run(args):
    t = load(args.workbook)
    if t.version != SUPPORTED_VERSION:
        print(f"warning: workbook is v{t.version}, the port mirrors v{SUPPORTED_VERSION}. "
              "Use --engine excel, or rerun tests/compare.py first.", file=sys.stderr)
    df = read_points(args.input)
    if args.fetch_retention or args.fetch_grid:
        import geopandas as gpd
        if not isinstance(df, gpd.GeoDataFrame) or df.geometry.isna().all():
            sys.exit("--fetch-retention/--fetch-grid need point geometry: an x/y "
                      "column pair in the csv, or a gpkg/shp/geo-parquet input")
    if args.fetch_retention:
        from .retention import join_retention
        joined = join_retention(df)
        df["retention_pct"] = joined["retention_pct"].to_numpy()
        missing_ret = df["retention_pct"].isna().sum()
        if missing_ret:
            print(f"warning: {missing_ret} point(s) got no retention value (outside "
                  "the layer, or on a cell boundary) and will be blank", file=sys.stderr)
    if args.fetch_grid:
        from .grid import grid_for_points
        joined = grid_for_points(df)
        df["grid"] = joined["grid"].to_numpy()
        missing_grid = df["grid"].isna().sum()
        if missing_grid:
            print(f"warning: {missing_grid} point(s) fell outside the 609-cell grid "
                  "(outside Denmark) and got no grid id", file=sys.stderr)
    missing = [c for c in REQUIRED if c not in df.columns]
    for col, flag in (("retention_pct", "--fetch-retention"), ("grid", "--fetch-grid")):
        if col not in df.columns:
            missing.append(f"{col} (or pass {flag} with point geometry)")
    if missing:
        sys.exit(f"missing columns: {', '.join(missing)}")
    if "ammonium_pct" in df.columns and df["ammonium_pct"].notna().any():
        print("warning: ammonium_pct is set. The workbook does not change the organic share "
              "with it, so mineral + organic need not add up to total N. See docs.", file=sys.stderr)
    pairs = list(split_rows(df))
    names = [o[0] for o in OUTPUTS]
    if args.engine == "python":
        res = [compute(s, r, t) for s, r in pairs]
    else:
        res = [None] * len(pairs)
        batches = list(_excel_batches(pairs))
        recs = run_excel(args.workbook, [(b[0][1], [m[2] for m in b]) for b in batches], t)
        for rec in recs:
            i = batches[int(rec["case"])][int(rec["slot"])][0]
            ok = rec["leaching"] not in ("", "#ERR")
            res[i] = {"status": "ok" if ok else "blank in Excel",
                      **{k: pd.to_numeric(rec[k], errors="coerce") for k in names}}
    out = df.copy()
    res_df = pd.DataFrame(res, index=df.index)
    for c in res_df.columns:
        out["out_" + c if c in df.columns else c] = res_df[c]
    if args.solve:
        target = None if args.target is None else float(args.target)
        sol = pd.DataFrame([solve_mineral_n(s, r, t, target) for s, r in pairs], index=df.index)
        out["n_for_target"] = sol["n_for_target"]
        out["target_discharge"] = sol["target_discharge"]
        out["solve_status"] = sol["status"]
    write_points(out, args.output)
    print(f"{len(out)} rows -> {args.output}; status: {res_df['status'].str[:40].value_counts().to_dict()}")


def main():
    ap = argparse.ArgumentParser(prog="nuar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="compute leaching and discharge for a point table")
    r.add_argument("input", help="csv, parquet, gpkg or shp with one row per point and crop")
    r.add_argument("-o", "--output", required=True)
    r.add_argument("--workbook", default="/mnt/d/NUAR/Copy of NUAR-regneark (SEGES).xlsx")
    r.add_argument("--engine", choices=("python", "excel"), default="python")
    r.add_argument("--solve", action="store_true",
                   help="also find the spring mineral N that meets a target discharge")
    r.add_argument("--fetch-retention", action="store_true",
                   help="fill retention_pct from the national UMR retention layer "
                        "(geodata.fvm.dk WFS); needs point geometry (x/y columns, or "
                        "gpkg/shp/geo-parquet input)")
    r.add_argument("--fetch-grid", action="store_true",
                   help="fill grid (the DMI 10 km climate cell id) from each point's "
                        "own coordinates; needs point geometry, like --fetch-retention. "
                        "See nuar/grid.py for how the id is derived")
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
