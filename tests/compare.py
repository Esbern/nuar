"""Run random scenarios through real Excel and through the port, and compare."""
import collections
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(Path(__file__).parent))
from make_cases import make_cases, make_targeted
from nuar.excel import run_excel, OUTPUTS
from nuar.model import compute
from nuar.tables import load

book, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
targeted = len(sys.argv) > 4
t = load(book)
cases = (make_targeted if targeted else make_cases)(t, n, seed)
cache = Path(__file__).parent / f"oracle_{n}_{seed}{'_t' if targeted else ''}.pkl"
if cache.exists():
    xl = pickle.loads(cache.read_bytes())
else:
    xl = run_excel(book, cases, t)
    cache.write_bytes(pickle.dumps(xl))

names = [o[0] for o in OUTPUTS]
bad = collections.Counter(); examples = {}
both_ok = both_blank = only_xl = only_py = 0
worst = 0
for rec in xl:
    site, rows = cases[int(rec["case"])]
    row = rows[int(rec["slot"])]
    m = compute(site, row, t)
    x = rec["leaching"]
    x_ok = x not in ("", "#ERR")
    if x_ok and m["status"] == "ok":
        both_ok += 1
    elif not x_ok and m["status"] != "ok":
        both_blank += 1
    elif x_ok:
        only_xl += 1; examples.setdefault("only_excel", (rec, m["status"], site, row))
    else:
        only_py += 1; examples.setdefault("only_python", (rec, m, site, row))
    if m["status"].startswith("site"):
        continue
    for k in names:
        xv = rec[k]
        if xv in ("", "#ERR") or k not in m:
            continue
        try:
            xv = float(xv)
        except ValueError:
            continue
        d = abs(xv - m[k])
        if d > 1e-6 * max(1, abs(xv)):
            bad[k] += 1
            examples.setdefault(k, (rec[k], m[k], rec["case"], rec["slot"], site, row))
        if k == "leaching":
            worst = max(worst, d)
print(f"rows {len(xl)}  both computed {both_ok}  both blank {both_blank}  only excel {only_xl}  only python {only_py}")
print("max abs leaching diff", worst)
print("mismatches", dict(bad))
for k, v in list(examples.items())[:6]:
    print(k, json.dumps(v, ensure_ascii=False, default=str)[:1100])
