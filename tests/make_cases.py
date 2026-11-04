"""Random scenarios that exercise every branch of the workbook."""
import random


def valid_covers(t, crop):
    """Covers the workbook accepts after this crop (Vpldkat1 column 'gyldig')."""
    from nuar.tables import norm_key
    out = []
    for code in t.cover_name:
        ck = t.tab["HovedafgrKat"].get(norm_key(crop))
        if ck is None:
            continue
        row = t.tab["Vpldkat1"].get(int(f"{130 if ck[2] == 13 else ck[2]}{code}"))
        if row is not None and row[6] != "Ugyldig":
            out.append(code)
    return out


def make_cases(t, n_sites, seed=1):
    rnd = random.Random(seed)
    jb_sub = {1: "Diluvialsand", 2: "Litorina sand", 3: "Diluvialsand", 4: "Morænesand",
              5: "Moræneler", 6: "Moræneler", 7: "Moræneler", 11: "Ferskvandssand"}
    good = [c for c, r in t.tab["TabAfgrnr"].items() if r[3] == 1]
    grids = list(t.tab["GridTab"])
    crops = [c for c in t.tab["TabAfgrnr"]]
    common = [1, 2, 3, 5, 7, 10, 11, 13, 14, 22, 21, 19, 25, 151, 152, 160, 216, 218, 252, 263, 266, 275, 276]
    common = [c for c in common if c in t.crop_name] or crops
    covers = list(t.cover_name)
    usual = [968, 968, 968, 9680, 4000, 921, 11, 22, 3000]
    usual = [c for c in usual if c in t.cover_name]
    dates = [k for k in t.tab["DatoEfgrKorr"] if isinstance(k, str)]
    sub = ["Moræneler", "Morænesand", "Diluvialsand", "Flyvesand", "Litorina sand", "Yoldia sand", "Ferskvandssand"]
    manure = ["Svinegylle", "Kvæggylle", "Fjerkrægylle", "Fjerkrægødning", "Dybstrøelse", "Biogasgylle"]

    def crop():
        return rnd.choice(common) if rnd.random() < 0.6 else rnd.choice(good)

    def cover():
        return rnd.choice(usual) if rnd.random() < 0.7 else rnd.choice(covers)

    def amount(*opts):
        return rnd.choice(opts) if rnd.random() < 0.6 else None

    cases = []
    for _ in range(n_sites):
        jb = rnd.choice([1, 2, 3, 4, 5, 6, 7, 11])
        low = rnd.choices([None, "Lavbund (minerogen)", "Lavbund (organogen)"], [8, 1, 1])[0]
        site = dict(year=rnd.choice([2025, 2027, 2030]), grid=rnd.choice(grids),
                    retention_pct=rnd.choice([0, 40, 70, 85]),
                    n_level_scope=rnd.choice(["Høstår", "Alle 3 år"]), jb=jb,
                    irrigated=rnd.random() < 0.3, lowland=low,
                    c_horizon=jb_sub[jb] if rnd.random() < 0.85 else rnd.choice(sub),
                    manure_type=rnd.choice(manure))
        if rnd.random() < 0.15:
            site["manure_type"] = "Anden organisk"
            site["ammonium_pct"], site["utilisation_pct"] = rnd.choice([(40, 60), (75, 80), (10, 40)])
        elif rnd.random() < 0.1:
            site["ammonium_pct"] = rnd.choice([30, 65])
        rows = []
        for _ in range(5):
            a, b, c = crop(), crop(), crop()
            pick = lambda k: rnd.choice(valid_covers(t, k) or [cover()]) if rnd.random() < 0.9 else cover()
            r = dict(crop=a, cover=pick(a), prev_crop=b, prev_cover=pick(b),
                     prev2_crop=c, prev2_cover=pick(c))
            if rnd.random() < 0.5:
                r["catch_crop_date"] = rnd.choice(dates)
            r["early_sowing"] = rnd.random() < 0.15
            r["intermediate_crop"] = rnd.random() < 0.15
            r["precision"] = rnd.random() < 0.15
            if rnd.random() < 0.25:
                r["n_level_pct"] = rnd.choice([70, 85, 110])
            for pre in ("", "prev_", "prev2_"):
                r[pre + "min_spring"] = amount(0, 40, 120, 200)
                r[pre + "min_autumn"] = amount(0, 20, 40)
                r[pre + "manure_spring"] = amount(0, 60, 170)
                r[pre + "manure_autumn"] = amount(0, 30)
                r[pre + "grazing"] = amount(0, 50, 120)
            if rnd.random() < 0.1:
                r["runoff_summer"] = rnd.choice([0, 40, 90])
                r["runoff_winter"] = rnd.choice([200, 400])
                r["runoff_winter_prev"] = rnd.choice([0, 300])
            rows.append(r)
        cases.append((site, rows))
    return cases


def make_targeted(t, n_sites, seed=1):
    """Valid sites and rotations aimed at the measures and the maize factors."""
    rnd = random.Random(seed)
    grids = list(t.tab["GridTab"])
    pairs = {1: (6, "Moræneler"), 2: (1, "Diluvialsand"), 3: (1, "Diluvialsand"),
             4: (6, "Moræneler"), 5: (6, "Moræneler")}
    dates = ["9. aug. el. før", "20. aug.", "7. sept.", "1. okt.", "28. okt. el. efter"]
    cases = []
    for _ in range(n_sites):
        grid = rnd.choice(grids)
        jb, sub = pairs[t.tab["GridTab"][grid][1]]
        site = dict(year=2027, grid=grid, retention_pct=rnd.choice([40, 70]), n_level_scope="Høstår",
                    jb=jb, irrigated=False, c_horizon=sub, lowland=None, manure_type="Kvæggylle")
        rows = []
        for _ in range(5):
            kind = rnd.choice(["winter", "maize_catch", "maize_grass", "barley_catch"])
            n = rnd.choice([0, 60, 79, 80, 81, 120, 200])
            if kind == "winter":
                r = dict(crop=rnd.choice([10, 11, 13, 14]), cover=11, prev_crop=rnd.choice([1, 10, 11, 22]),
                         prev_cover=rnd.choice([11, 968, 22, 4000]), prev2_crop=1, prev2_cover=968,
                         early_sowing=rnd.random() < 0.5, intermediate_crop=rnd.random() < 0.5,
                         precision=rnd.random() < 0.4, min_spring=n)
            elif kind == "maize_catch":
                r = dict(crop=rnd.choice([5, 19, 216, 218]), cover=rnd.choice([4000, 968]), prev_crop=216,
                         prev_cover=rnd.choice([968, 9680, 4000]), prev2_crop=216, prev2_cover=968,
                         precision=rnd.random() < 0.3, min_spring=n)
                if r["cover"] == 968 and rnd.random() < 0.7:
                    r["catch_crop_date"] = rnd.choice(dates)
            elif kind == "maize_grass":
                r = dict(crop=rnd.choice([5, 19, 216, 218]), cover=rnd.choice([4000, 968]),
                         prev_crop=rnd.choice([260, 263, 266]), prev_cover=260,
                         prev2_crop=rnd.choice([260, 263, 1]), prev2_cover=260, min_spring=n,
                         manure_spring=rnd.choice([0, 100]))
            else:
                r = dict(crop=rnd.choice([1, 2, 3]), cover=rnd.choice([968, 9680]), prev_crop=1,
                         prev_cover=rnd.choice([968, 9680]), prev2_crop=1, prev2_cover=968,
                         catch_crop_date=rnd.choice(dates), precision=rnd.random() < 0.4, min_spring=n)
            rows.append(r)
        cases.append((site, rows))
    return cases
