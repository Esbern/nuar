# nuar

Runs the SEGES NUAR spreadsheet (v1.3) for a table of points, either through
real Excel or through a Python port checked against it.

Read [docs/NUAR_explained.md](docs/NUAR_explained.md) first.

## Setup

```bash
mamba create -n nuar -c conda-forge python=3.12 openpyxl pandas geopandas pyogrio pytest
```

The workbook is not included. The default path is
`/mnt/d/NUAR/Copy of NUAR-regneark (SEGES).xlsx`; use `--workbook` for another.

## Run

```bash
mamba run -n nuar python -m nuar run examples/points_template.csv -o result.csv
```

| Option | Effect |
|---|---|
| `--engine python` | the port (default), about 55,000 rows/s |
| `--engine excel` | real Excel through WSL, about 3 sites/s (up to 5 crop rows per site); needs Excel on Windows |
| `--solve` | also find the spring mineral N that meets a target discharge |
| `--target 12` | target in kg N/ha (default: the spring-barley reference) |

Input can be csv, parquet, gpkg or shp. The Excel engine works on a temporary
copy, writes only to the unlocked input cells and never saves.

## Check against Excel

```bash
mamba run -n nuar python tests/compare.py "<workbook>" 1500 2
```

arguments: workbook, number of sites (five crop rows each), random seed.
