# nuar

Runs the SEGES NUAR spreadsheet (v1.3) for a table of points, either through
real Excel or through a Python port checked against it.

Read [docs/NUAR_explained.md](docs/NUAR_explained.md) first.

## Setup

```bash
mamba create -n nuar -c conda-forge python=3.12 openpyxl pandas geopandas pyogrio pytest
```

The workbook is not included. Export its tables once, and the Python engine
runs without it:

```bash
mamba run -n nuar python -m nuar export-tables "NUAR-regneark (SEGES).xlsx"
```

This writes `data/tables/tables.json` (everything the model reads) and one CSV
per table in `data/tables/csv/`, for reading. Like the cache, the export is
git-ignored: the tables are SEGES's and are not redistributed here. Without an
export, the workbook is read from `--workbook` (default
`/mnt/d/NUAR/Copy of NUAR-regneark (SEGES).xlsx`); the Excel engine always needs it.

## Run

```bash
mamba run -n nuar python -m nuar run examples/points_template.csv -o result.csv

# or, from real coordinates alone, with retention and the climate grid id
# both fetched automatically:
mamba run -n nuar python -m nuar run examples/points_fetch_retention.csv -o result.csv \
    --fetch-retention --fetch-grid
```

| Option | Effect |
|---|---|
| `--engine python` | the port (default), about 55,000 rows/s |
| `--engine excel` | real Excel through WSL, about 3 sites/s (up to 5 crop rows per site); needs Excel on Windows |
| `--solve` | also find the spring mineral N that meets a target discharge |
| `--target 12` | target in kg N/ha (default: the spring-barley reference) |
| `--fetch-retention` | fill `retention_pct` from the national UMR retention layer (live WFS, no login) |
| `--fetch-grid` | fill `grid` (the DMI 10 km climate cell id) from each point's own coordinates — see `nuar/grid.py` |

Both `--fetch-*` options need point geometry: an `x`/`y` column pair in a csv
(EPSG:25832 if values look like metres, else lon/lat), or a gpkg/shp/geo-parquet
input.

Input can be csv, parquet, gpkg or shp. The Excel engine works on a temporary
copy, writes only to the unlocked input cells and never saves.

See [docs/data_sources.md](docs/data_sources.md) for where to get the
remaining required inputs (soil class, subsoil, lowland, crop/cover).

## Check against Excel

```bash
mamba run -n nuar python tests/compare.py "<workbook>" 1500 2
```

arguments: workbook, number of sites (five crop rows each), random seed.
