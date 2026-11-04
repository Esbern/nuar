"""Load the lookup tables and parameters out of the SEGES NUAR workbook.

The tables are read from the user's own copy of the workbook and cached in
data/ (git-ignored). They are never redistributed with this code.
"""
from __future__ import annotations

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


def load(xlsx: Path, cache: Path | None = None) -> Tables:
    xlsx = Path(xlsx)
    cache = Path(cache) if cache else Path(__file__).parents[1] / "data" / "tables.pkl"
    if cache.exists() and cache.stat().st_mtime >= xlsx.stat().st_mtime:
        return pickle.loads(cache.read_bytes())
    t = build(xlsx)
    cache.parent.mkdir(exist_ok=True)
    cache.write_bytes(pickle.dumps(t))
    return t
