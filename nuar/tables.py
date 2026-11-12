"""Load the lookup tables and parameters out of the SEGES NUAR workbook.

The tables are read from the user's own copy of the workbook, or from an export
of them (`python -m nuar export-tables <workbook>`): data/tables/tables.json with
everything the model reads, and one CSV per table for reading. With an export the
Python engine runs without the workbook. Both the cache and the export live in
data/ (git-ignored); they are SEGES's tables and are not redistributed with this code.
"""
from __future__ import annotations

import csv
import json
import pickle
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from openpyxl.utils import range_boundaries

SUPPORTED_VERSION = "1.3"
TABLES = (
    "TabJB JBgrp HdgUdn DatoEfgrKorr NL5AfgrParm Chorisontnr GridTab GeoregNavn "
    "SoilidTab TabFixN TabDat TabAfgrnr VpldKode Vpldkat1 Vpldkat2 TabNorm "
    "TabAfgr HovedafgrKat AfstrDat"
).split()


def norm_key(v):
    """Excel's VLOOKUP treats 1 and 1.0 as equal and ignores text case."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        return v.casefold()
    return v


@dataclass
class Tables:
    tab: dict          # table name -> {key: row tuple}, first match wins as in VLOOKUP
    par: dict          # NLES5 parameters from Normer, keyed by cell row, e.g. 'C60'
    konst: dict        # scalar effects (catch crop, precision, maize, ...)
    grid_ids: dict     # names for the dropdowns
    crop_name: dict    # crop code -> Opslag navn (the text the worksheet expects)
    cover_name: dict   # cover code -> VpldNavn
    version: str

    def has(self, table, key):
        return norm_key(key) in self.tab[table]

    def vl(self, table, key, col):
        """VLOOKUP(key, table, col, FALSE). A blank result reads as 0, as in Excel."""
        row = self.tab[table].get(norm_key(key))
        if row is None:
            raise KeyError((table, key))
        v = row[col - 1]
        return 0 if v is None else v


def _read_range(ws, ref):
    c0, r0, c1, r1 = range_boundaries(ref.replace("$", ""))
    return [tuple(c.value for c in row)
            for row in ws.iter_rows(min_row=r0, max_row=r1, min_col=c0, max_col=c1)]


def build(xlsx: Path) -> Tables:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    version = str(wb["NUAR-regneark"]["Q5"].value)
    names = {n: d.attr_text for n, d in wb.defined_names.items()}
    tab = {}
    for name in TABLES:
        sheet, ref = names[name].rsplit("!", 1)
        table = {}
        for row in _read_range(wb[sheet.strip("'")], ref):
            if row[0] is not None:
                table.setdefault(norm_key(row[0]), row)
        tab[name] = table
    normer, regn = wb["Normer"], wb["Regn"]
    par = {f"C{r}": normer[f"C{r}"].value for r in list(range(60, 64)) + list(range(66, 83))}
    konst = {"efgr": regn["C5"].value, "mellem": regn["C6"].value, "tsaa": regn["C7"].value,
             "majs": normer["C84"].value, "praec": normer["B88"].value}
    return Tables(tab, par, konst,
                  {"jb": [k for k in tab["TabJB"]]},
                  {r[1]: r[0] for r in tab["TabDat"].values() if r[1] is not None},
                  {r[2]: r[0] for r in tab["VpldKode"].values()},
                  version)


EXPORT_FORMAT = 1
DEFAULT_EXPORT = Path(__file__).parents[1] / "data" / "tables"


def export(t: Tables, folder: Path, source: str = "") -> Path:
    """Write the tables as data/tables/tables.json (what the model reads) and csv/<table>.csv."""
    folder = Path(folder)
    (folder / "csv").mkdir(parents=True, exist_ok=True)
    doc = {"format": EXPORT_FORMAT, "nuar_version": t.version, "source": source,
           "tables": {name: [list(r) for r in rows.values()] for name, rows in t.tab.items()},
           "par": t.par, "konst": t.konst, "grid_ids": t.grid_ids,
           "crop_name": [[k, v] for k, v in t.crop_name.items()],
           "cover_name": [[k, v] for k, v in t.cover_name.items()]}
    path = folder / "tables.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    for name, rows in doc["tables"].items():
        with open(folder / "csv" / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([f"c{i + 1}" for i in range(max(len(r) for r in rows))])
            w.writerows(rows)
    return path


def load_export(folder: Path) -> Tables:
    """Tables from an export (a folder holding tables.json, or the file itself)."""
    path = Path(folder)
    path = path / "tables.json" if path.is_dir() else path
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("format") != EXPORT_FORMAT:
        raise ValueError(f"{path}: export format {doc.get('format')}, expected {EXPORT_FORMAT}")
    tab = {}
    for name, rows in doc["tables"].items():
        table = {}
        for row in rows:
            table.setdefault(norm_key(row[0]), tuple(row))
        tab[name] = table
    return Tables(tab, doc["par"], doc["konst"], doc["grid_ids"],
                  {k: v for k, v in doc["crop_name"]}, {k: v for k, v in doc["cover_name"]},
                  doc["nuar_version"])


def load(xlsx: Path, cache: Path | None = None) -> Tables:
    """Tables from the workbook (cached), or from an export when given a folder or a .json."""
    xlsx = Path(xlsx)
    if xlsx.is_dir() or xlsx.suffix.lower() == ".json":
        return load_export(xlsx)
    cache = Path(cache) if cache else Path(__file__).parents[1] / "data" / "tables.pkl"
    if cache.exists() and cache.stat().st_mtime >= xlsx.stat().st_mtime:
        return pickle.loads(cache.read_bytes())
    t = build(xlsx)
    cache.parent.mkdir(exist_ok=True)
    cache.write_bytes(pickle.dumps(t))
    return t
