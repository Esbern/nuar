"""Check the port against the worked examples stored in the hidden sheet
'Tabel Kvælstofudvaskning'. They were pasted as values by SEGES for one site."""
import collections
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).parents[1]))
from nuar.excel import run_excel
from nuar.model import compute
from nuar.tables import load

book = sys.argv[1]
t = load(book)
SITE = dict(year=2027, grid=10315, retention_pct=70, n_level_scope="Høstår", jb=6,
            irrigated=False, c_horizon="Moræneler", lowland=None, manure_type="Svinegylle")
ws = openpyxl.load_workbook(book, data_only=True, read_only=True)["Tabel Kvælstofudvaskning"]
crop_by_name = {v.casefold(): k for k, v in t.crop_name.items()}
crop_by_name.update({n.split(" ", 1)[1].casefold(): c for n, c in
                     ((v, k) for k, v in t.crop_name.items())})
cover_by_name = {" ".join(v.split()).casefold(): k for k, v in t.cover_name.items()}


def cover_code(name):
    if not name:
        return None
    key = " ".join(str(name).split()).casefold()
    if key in cover_by_name:
        return cover_by_name[key]
    head = key.split(" ")[0]
    return int(head) if head.isdigit() and int(head) in t.cover_name else None


res = collections.Counter(); diffs = []; todo = []
for r in ws.iter_rows(min_row=7, values_only=True):
    if r[0] is None or not isinstance(r[13], (int, float)):
        continue
    if r[17]:                       # free-text remark: the inputs are not all recorded
        res["skipped: remark"] += 1
        continue
    code = crop_by_name.get(str(r[1]).casefold()), crop_by_name.get(str(r[3]).casefold())
    row = dict(crop=int(r[0]), cover=cover_code(r[7]), prev_crop=code[1], prev_cover=cover_code(r[4]),
               prev2_crop=code[0], prev2_cover=cover_code(r[2]))
    if r[12] not in (0, None, ""):
        row["catch_crop_date"] = r[12]
    if None in row.values() and row.get("cover") is None:
        res["skipped: cover name"] += 1
        continue
    m = compute(SITE, row, t)
    if m["status"] != "ok":
        res["not computable"] += 1
        continue
    todo.append((row, r, m))
    d = m["leaching"] - r[13]
    res["port = stored" if abs(d) < 0.01 else "port != stored"] += 1
print(dict(res))
chunks = [todo[i:i + 5] for i in range(0, len(todo), 5)]
xl = run_excel(book, [(SITE, [c[0] for c in ch]) for ch in chunks], t)
agree = stale = other = 0
for rec in xl:
    row, r, m = chunks[int(rec["case"])][int(rec["slot"])]
    x = float(rec["leaching"]) if rec["leaching"] not in ("", "#ERR") else None
    if x is None:
        other += 1
        continue
    agree += abs(x - m["leaching"]) < 1e-6
    stale += abs(x - r[13]) >= 0.01
    if abs(x - m["leaching"]) >= 1e-6:
        print("PORT != EXCEL", r[6], r[7], x, m["leaching"])
print(f"current Excel = port: {agree} of {len(xl)}; current Excel != stored table: {stale}; Excel blank: {other}")
