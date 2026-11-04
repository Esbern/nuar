"""How many compared rows actually reached each branch of the model."""
import collections
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(Path(__file__).parent))
from make_cases import make_cases
from nuar.model import MAIZE, compute
from nuar.tables import load

book, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
t = load(book)
cases = make_cases(t, n, seed)
xl = pickle.loads((Path(__file__).parent / f"oracle_{n}_{seed}.pkl").read_bytes())
c = collections.Counter()
for rec in xl:
    site, rows = cases[int(rec["case"])]
    r = rows[int(rec["slot"])]
    m = compute(site, r, t)
    if m["status"] != "ok":
        c["blank: " + m["status"].split(":")[0]] += 1
        continue
    f = m["cover_factor"]
    add = lambda k, cond: c.update({k: 1} if cond else {})
    add("catch crop effect", r["cover"] in (968, 9680) and f < 1)
    add("catch crop with date", r["cover"] in (968, 9680) and r.get("catch_crop_date"))
    add("no cover effect", abs(f - 1) < 1e-12)
    add("intermediate crop effect", r["intermediate_crop"] and abs(f - 0.8) < 0.04 and r["cover"] not in (968, 9680))
    add("early sowing effect", r["early_sowing"] and not r["intermediate_crop"] and abs(f - 0.8) < 0.04 and r["cover"] not in (968, 9680))
    add("precision effect", r["precision"] and abs((f / round(f, 2)) - 1) > 1e-9 or abs(f - 0.96) < 1e-9 or abs(f - 0.768) < 1e-9)
    add("maize", r["crop"] in MAIZE)
    add("maize after catch crop (0.72)", r["crop"] in MAIZE and r["prev_cover"] == 968)
    add("N fixation > 0, harvest year", m["n_fixation"] > 0)
    add("N fixation > 0, earlier years", m["prev_n_fixation"] + m["prev2_n_fixation"] > 0)
    add("grazing", (r.get("grazing") or 0) > 0)
    add("autumn manure", (r.get("manure_autumn") or 0) > 0)
    add("Anden organisk", site["manure_type"] == "Anden organisk")
    add("ammonium override", site.get("ammonium_pct") is not None)
    add("lowland", site.get("lowland") is not None)
    add("sandy (JB 1, 3)", site["jb"] in (1, 3))
    add("all 3 years N level", site["n_level_scope"] == "Alle 3 år" and r.get("n_level_pct"))
    add("runoff override", r.get("runoff_summer") is not None)
for k, v in sorted(c.items()):
    print(f"{v:6} {k}")
