"""Run cases through the real workbook with Excel on the Windows side of WSL."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import uuid
from pathlib import Path

ROW_CELLS = {
    "crop": "L", "cover": "N", "prev_crop": "G", "prev_cover": "I",
    "prev2_crop": "B", "prev2_cover": "D", "catch_crop_date": "P",
    "early_sowing": "R", "intermediate_crop": "T", "precision": "V", "n_level_pct": "X",
    "min_spring": "AO", "min_autumn": "AQ", "manure_spring": "AS",
    "manure_autumn": "AU", "grazing": "AW",
    "prev_min_spring": "BN", "prev_min_autumn": "BP", "prev_manure_spring": "BR",
    "prev_manure_autumn": "BT", "prev_grazing": "BV",
    "prev2_min_spring": "CF", "prev2_min_autumn": "CH", "prev2_manure_spring": "CJ",
    "prev2_manure_autumn": "CL", "prev2_grazing": "CN",
    "runoff_summer": "CW", "runoff_winter": "DA", "runoff_winter_prev": "DE",
}
SITE_CELLS = {
    "year": "B5", "grid": "D5", "retention_pct": "I5", "n_level_scope": "L5",
    "jb": "B8", "irrigated": "D8", "c_horizon": "G8", "lowland": "I8",
    "manure_type": "B11", "utilisation_pct": "G11", "ammonium_pct": "L11",
}
OUTPUTS = [
    ("leaching", "NUAR-regneark", "AA"), ("discharge", "NUAR-regneark", "AC"),
    ("reference_discharge", "NUAR-regneark", "AF"), ("pct_of_reference", "NUAR-regneark", "AH"),
    ("n_norm", "NUAR-regneark", "AK"), ("n_norm_undersown", "NUAR-regneark", "AM"),
    ("n_mineral_spring", "NUAR-regneark", "AY"), ("n_organic_spring", "NUAR-regneark", "BA"),
    ("n_mineral_autumn", "NUAR-regneark", "BC"), ("n_mineral_grazing", "NUAR-regneark", "BE"),
    ("n_fixation", "NUAR-regneark", "BG"), ("prev_total_n", "NUAR-regneark", "BX"),
    ("prev_n_fixation", "NUAR-regneark", "BZ"), ("prev2_total_n", "NUAR-regneark", "CP"),
    ("prev2_n_fixation", "NUAR-regneark", "CR"), ("runoff_summer", "NUAR-regneark", "CU"),
    ("runoff_winter", "NUAR-regneark", "CY"), ("runoff_winter_prev", "NUAR-regneark", "DC"),
    ("n_conc_mg_l", "NUAR-regneark", "DG"), ("crop_effect_c", "NUAR-regneark", "DT"),
    ("n_effect", "NUAR-regneark", "ED"), ("cover_factor", "Regn", "ES"),
]
SLOTS = 5
_MAX_TEXT = {"early_sowing", "intermediate_crop", "precision"}


def _win(cmd):
    return subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True, check=True).stdout.strip()


def _wslpath(p):
    return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True,
                          check=True).stdout.strip()


def _site_cells(site, t):
    out = {}
    for k, cell in SITE_CELLS.items():
        v = site.get(k)
        if k == "irrigated":
            v = "Ja" if v else "Nej"
        out[cell] = v
    return out


def _row_cells(row, t):
    out = {}
    for k, col in ROW_CELLS.items():
        v = row.get(k)
        if v is None or v == "":
            continue
        if k.endswith("crop") and k != "intermediate_crop":
            v = t.crop_name[int(v)]
        elif k.endswith("cover"):
            v = t.cover_name[int(v)]
        elif k in _MAX_TEXT:
            if not v:
                continue
            v = "Ja"
        out[col] = v
    return out


def run_excel(workbook, cases, t):
    """cases: [(site dict, [up to 5 row dicts])]. One recalculation per case."""
    win_tmp = _win("[IO.Path]::GetTempPath()")
    wsl_tmp = Path(subprocess.run(["wslpath", "-u", win_tmp], capture_output=True, text=True,
                                  check=True).stdout.strip())
    tag = uuid.uuid4().hex
    job_f, out_f = wsl_tmp / f"nuar_{tag}.json", wsl_tmp / f"nuar_{tag}.tsv"
    ps1 = wsl_tmp / f"nuar_{tag}.ps1"
    book = wsl_tmp / f"nuar_{tag}_src.xlsx"
    shutil.copy2(Path(__file__).parents[1] / "excel" / "run_nuar.ps1", ps1)
    shutil.copy2(workbook, book)
    job = {"outputs": [{"name": n, "sheet": s, "col": c} for n, s, c in OUTPUTS],
           "cases": [{"site": _site_cells(s, t), "rows": [_row_cells(r, t) for r in rows]}
                     for s, rows in cases]}
    job_f.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    try:
        p = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", _wslpath(ps1),
             "-Workbook", _wslpath(book), "-JobFile", _wslpath(job_f), "-Out", _wslpath(out_f)],
            capture_output=True, text=True)
        if p.returncode != 0 or not out_f.exists():
            raise RuntimeError(p.stdout + p.stderr)
        with out_f.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
        print(p.stdout.strip())
        return rows
    finally:
        for f in (job_f, out_f, ps1, book):
            f.unlink(missing_ok=True)
