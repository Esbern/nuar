"""Python port of the calculation sheet (Regn) of the SEGES NUAR workbook, v1.3.

Comments give the Regn column each value mirrors, so a difference from Excel
can be traced to one formula. The port keeps the workbook's behaviour, oddities
included. See docs/NUAR_explained.md.

    Y = (tau*(year-1991) + (mu + theta*N + C)^1.5 * P * S * rho) * F_cover * F_maize * F_maize_grass
"""
from __future__ import annotations

from .tables import Tables

E1, E2 = 2.718281828, 2.71828182845904   # both are used in the workbook
MAIZE = (5, 19, 216, 218)
MAIZE_DEFAULT_CATCH = 0.388835           # Regn!C4: maize without a date, i.e. 1 Oct
_NUM = ("min_spring", "min_autumn", "manure_spring", "manure_autumn", "grazing")


class NotComputable(Exception):
    """The workbook would show a blank result (#N/A, #NUM! or a crop that cannot be computed)."""


def _blank(v):
    if v is None or v == "":
        return True
    return isinstance(v, float) and v != v  # NaN, e.g. a pandas-missing numeric


def _missing(name, v):
    if _blank(v):
        raise TypeError(f"{name} is missing")
    return v


def _nz(v):
    return 0 if _blank(v) else v


def _try(t, table, key, col, default=0):
    try:
        return t.vl(table, key, col)
    except KeyError:
        return default


def typejord(site, t: Tables):
    """Regneark!L8: georegion + JB group + subsoil, or the lowland class."""
    region = t.vl("GridTab", site["grid"], 2)
    low = site.get("lowland")
    if low == "Lavbund (minerogen)":
        return int(f"{region}998")
    if low == "Lavbund (organogen)":
        return int(f"{region}999")
    return int(f"{region}0{t.vl('JBgrp', site['jb'], 2)}{t.vl('Chorisontnr', site['c_horizon'], 2)}")


def _site(site, t: Tables):
    """Everything that is shared by all crops on one site."""
    jb = site["jb"]
    p = t.par
    s = {"jb": jb, "tj": typejord(site, t), "grid": site["grid"],
         "normgrp": t.vl("TabJB", jb, 6 + (1 if site.get("irrigated") else 0))}   # B13
    manure = site.get("manure_type") or "Svinegylle"
    ammonium_base = t.vl("HdgUdn", manure, 6) * 100                               # I11, O7
    s["ammonium_org"] = 100 - ammonium_base                                       # 100 - I11
    amm = site.get("ammonium_pct")
    s["ammonium"] = ammonium_base if _blank(amm) else amm                         # O8
    s["all_years"] = site.get("n_level_scope") == "Alle 3 år"                     # L5
    s["retention"] = _missing("retention_pct", site["retention_pct"])
    s["tau"] = p["C60"] * (site["year"] - 1991)                                   # EO
    s["n_topsoil"] = t.vl("SoilidTab", s["tj"], 9)                                # CW
    s["clay"] = t.vl("SoilidTab", s["tj"], 3)                                     # DW
    s["S"] = 0 if s["clay"] == 0 else E2 ** (p["C76"] * s["clay"])                # DX
    sandy = jb in (1, 3)                                                          # DY
    c = ("C77", "C78", "C79") if sandy else ("C80", "C81", "C82")
    if s["clay"] == 0:
        s["d1"], s["d2"], s["v2"] = 0, 0, 0
    else:
        s["d1"], s["d2"], s["v2"] = p[c[0]], p[c[1]], p[c[2]]                     # DZ, EA, EB
    s["reference"] = _reference(s, t)
    return s


def _perc(s, summer, winter, winter_prev):
    """P: the drainage effect, EL * EM."""
    el = 1 - E1 ** ((-s["d1"] * summer) - (s["d2"] * winter))
    em = 0 if winter_prev == 0 else E1 ** (-s["v2"] * winter_prev)
    return el * em


def _runoff(s, t, code):
    key = int(f"{s['grid']}{s['tj']}{code}")
    return t.vl("AfstrDat", key, 8), t.vl("AfstrDat", key, 9)


def _reference(s, t: Tables):
    """HM: spring barley after spring barley, both with a catch crop on 20 Aug."""
    p = t.par
    nm = t.vl("TabNorm", 1, s["normgrp"] + 2) - 21                                # FQ
    n = s["n_topsoil"] * p["C70"] + nm * p["C67"] + p["C71"] * nm                 # GK
    summer, winter = _runoff(s, t, 1)
    add = (p["C63"] + 1.205144 * n + 1.6649999999999991) ** 1.5                   # HH
    mult = _perc(s, summer, winter, winter) * s["S"] * p["C62"]                   # HI
    return (s["tau"] + add * mult) * 0.55                                         # HM


def _n_norm(t, s, crop, cover, prior, prior_cover, level, biafgr_level):
    """V..AA (harvest year) and BK..BO (previous year)."""
    g = s["normgrp"] + 2
    base = _try(t, "TabNorm", crop, g)
    prec = -(_try(t, "TabNorm", prior, 15) * _try(t, "TabNorm", crop, 17)) \
        if t.has("TabNorm", prior) and t.has("TabNorm", crop) else 0
    catch = -21 if prior_cover == 968 else (-50 if prior_cover == 9680 else 0)
    und = 0 if cover < 943 else _try(t, "TabNorm", cover, g)
    return base * level, prec + catch, und * biafgr_level


def _bael(lock, mineral):
    """IF..IK: FBælgN, the share of N taken from the air at a given mineral N."""
    if lock < 2:
        return 1
    return min(max(-0.0015 * mineral + 0.6, 0), 0.6)


def _fix(t, s, code, gate, mineral):
    """One Nfix term of JD..JF. gate applies the IF(code<943,0,..) test."""
    if gate and code < 943:
        return 0
    ftype = _try(t, "TabFixN", code, 15)
    std = _try(t, "TabFixN", code, s["normgrp"] + 2)
    at_norm = _try(t, "TabFixN", code, s["normgrp"] + 8)
    if ftype == 3:
        return std
    corr = 0 if at_norm == 0 else _bael(ftype, mineral) / at_norm
    return corr * std


def compute_row(site_state, row, t: Tables):
    s, p = site_state, t.par
    crop, cover = int(_nz(row.get("crop"))), int(_nz(row.get("cover")))
    prev, prev_cover = int(_nz(row.get("prev_crop"))), int(_nz(row.get("prev_cover")))
    prev2, prev2_cover = int(_nz(row.get("prev2_crop"))), int(_nz(row.get("prev2_cover")))
    lvl_pct = row.get("n_level_pct")
    level = 1 if _blank(lvl_pct) else lvl_pct / 100                               # KvoteFak
    hist = level if s["all_years"] else 1                                         # AR, BL
    amm, org = s["ammonium"] * 0.01, s["ammonium_org"] * 0.01
    out = {}

    # --- N norms: V..AD, AQ..AX, BK..BR
    base, corr, und = _n_norm(t, s, crop, cover, prev, prev_cover, level, level)
    n_norm = max(base + corr, 0)                                                  # AA
    prev_base, prev_corr, prev_und = _n_norm(t, s, prev, prev_cover, prev2, prev2_cover, hist, hist)
    prev_norm = max(prev_base + prev_corr, 0)                                     # BO
    g = s["normgrp"] + 2
    prev2_norm = _try(t, "TabNorm", prev2, g) * hist                              # AU
    prev2_und = (0 if prev2_cover < 943 else _try(t, "TabNorm", prev2_cover, g)) * hist  # AX

    def supply(prefix, norm, undersown):
        v = {k: _nz(row.get(prefix + k)) for k in _NUM[2:]}
        ms = norm if _blank(row.get(prefix + "min_spring")) else row[prefix + "min_spring"]
        ma = undersown if _blank(row.get(prefix + "min_autumn")) else row[prefix + "min_autumn"]
        return ms, ma, v["manure_spring"], v["manure_autumn"], v["grazing"]

    ms, ma, gs, ga, gz = supply("", n_norm, und)
    ms1, ma1, gs1, ga1, gz1 = supply("prev_", prev_norm, prev_und)
    ms2, ma2, gs2, ga2, gz2 = supply("prev2_", prev2_norm, prev2_und)

    mn_spring = ms + gs * amm                                                     # DA
    mn_autumn = ma + ga * amm                                                     # DE
    mn_graze = gz * amm                                                           # DG
    org_spring = gs * org                                                         # DQ
    total1 = ms1 + gs1 * amm + gs1 * org + ma1 + ga1 * amm + ga1 * org + gz1      # DI
    total2 = ms2 + gs2 * amm + gs2 * org + ma2 + ga2 * amm + ga2 * org + gz2      # DJ

    # --- N fixation: HT..JF
    min2, min2u = ms2 + gs2 * amm + ma2 + ga2 * amm + gz2 * amm, ma2 + ga2 * amm + gz2 * amm
    min1, min1u = ms1 + gs1 * amm + ma1 + ga1 * amm + gz1 * amm, ma1 + ga1 * amm + gz1 * amm
    min0, min0u = ms + gs * amm + ma + ga * amm + gz * amm, ma + ga * amm + gz * amm
    f2 = _fix(t, s, prev2, False, min2) + _fix(t, s, prev2_cover, True, min2u)    # JD
    f1 = _fix(t, s, prev, False, min1) + _fix(t, s, prev_cover, True, min1u)      # JE
    f0 = _fix(t, s, crop, False, min0) + _fix(t, s, cover, True, min0u)           # JF

    out.update(reference_discharge=s["reference"] * (100 - s["retention"]) * 0.01,
               n_norm=n_norm, n_norm_undersown=und, n_mineral_spring=mn_spring,
               n_organic_spring=org_spring, n_mineral_autumn=mn_autumn,
               n_mineral_grazing=mn_graze, n_fixation=f0, prev_total_n=total1,
               prev_n_fixation=f1, prev2_total_n=total2, prev2_n_fixation=f2)

    n_effect = (s["n_topsoil"] * p["C70"] + mn_spring * p["C67"] + mn_autumn * p["C68"]
                + mn_graze * p["C69"] + p["C71"] * (total1 + total2) / 2 + f0 * p["C72"]
                + p["C73"] * (f1 + f2) / 2 + org_spring * p["C66"])               # DS
    out["n_effect"] = n_effect

    try:
        # --- crop effect C: CE..CV
        ce = t.vl("TabAfgrnr", prev2, 3)
        cf = t.vl("TabAfgrnr", prev, 2)
        cg = t.vl("VpldKode", t.cover_name[prev_cover] if prev_cover in t.cover_name else "", 3)
        ch = t.vl("HovedafgrKat", crop, 6)
        ci = t.vl("VpldKode", t.cover_name[cover] if cover in t.cover_name else "", 3)
        ck = t.vl("HovedafgrKat", crop, 3 + (1 if cf in (4, 5, 6) else 0))
        cl = _try(t, "NL5AfgrParm", ck, 2)
        cm = 130 if ck == 13 else ck
        cn = int(f"{cm}{ci}")
        if ci == 500 or 399 < crop < 650:
            co = t.vl("TabAfgrnr", crop, 7)
        elif 148 < crop < 157:
            co = 3
        else:
            co = t.vl("Vpldkat1", cn, 7)
        cp = t.vl("NL5AfgrParm", co, 3)
        if cf == 0:
            cq, cr = 0, 0
        else:
            if cf == 4:
                cq = 3
            elif cf in (1, 2) and cg == 6:
                cq = 3
            elif ce == 4:
                cq = 4
            elif cf == 1:
                cq = 1
            else:
                cq = 2
            cr = t.vl("NL5AfgrParm", cq, 4)
        ct = t.vl("TabAfgrnr", prev, 6) if prev_cover == 500 else t.vl("Vpldkat2", int(f"{ce}{cf}{cg}"), 7)
        cu = t.vl("NL5AfgrParm", ct, 5)
        C = cl + cp + cr + cu
        out["crop_effect_c"] = C

        # --- winter crop class theta: DT..DV
        dt = t.vl("HovedafgrKat", crop, 8) + _try(t, "HovedafgrKat", cover, 9)
        theta = 0 if dt == 0 else (1 if dt == 1 else p["C75"])

        # --- runoff: EC..EK
        ec = t.vl("TabAfgr", crop, 27)
        summer0, winter0 = _runoff(s, t, ec)
        winter_prev0 = _runoff(s, t, t.vl("TabAfgr", prev, 27))[1]
        out.update(runoff_summer=summer0, runoff_winter=winter0, runoff_winter_prev=winter_prev0)
        summer = summer0 if _blank(row.get("runoff_summer")) else row["runoff_summer"]
        winter = winter0 if _blank(row.get("runoff_winter")) else row["runoff_winter"]
        winter_prev = winter_prev0 if _blank(row.get("runoff_winter_prev")) else row["runoff_winter_prev"]
        P = _perc(s, summer, winter, winter_prev)

        # --- additive and multiplicative parts: EP, EQ
        if ch == 0:
            add = 0
        else:
            base_add = p["C63"] + theta * n_effect + C
            if base_add < 0:
                raise NotComputable("negative base in (mu+theta*N+C)^1.5")
            add = base_add ** 1.5
        mult = P * s["S"] * p["C62"]

        # --- measures: ER..EU
        er = t.vl("TabAfgr", crop, 41) * t.konst["praec"] if row.get("precision") else 0
        maize = crop in MAIZE
        date = row.get("catch_crop_date")
        if maize and _blank(date):
            korr = MAIZE_DEFAULT_CATCH
        else:
            korr = _try(t, "DatoEfgrKorr", date, 2, 1) if not _blank(date) else 1
        mellem_ok = t.vl("TabAfgrnr", crop, 5)
        if ci in (968, 9680) and ch not in (4, 5, 6, 7):
            f = 1 - t.konst["efgr"] * korr
        elif row.get("intermediate_crop") and co == 1 and mellem_ok == 1:
            f = 1 - t.konst["mellem"]
        elif row.get("early_sowing") and co == 1:
            f = 1 - t.konst["tsaa"]
        else:
            f = 1
        f_cover = f * (1 - er)
        out["cover_factor"] = f_cover
        f_maize = t.konst["majs"] if maize and prev_cover == 968 else 1
        f_grass = 1
        if ck == 11 and maize:
            f_grass = 0.0028 * mn_spring + 0.5599 if mn_spring <= 80 else 0.004 * mn_spring + 0.4639

        y = (s["tau"] + add * mult) * f_cover * f_maize * f_grass                 # EV
        if t.vl("TabAfgrnr", crop, 4) == 0:                                       # EW
            raise NotComputable("crop is marked as not computable")
        if y == 0:
            raise NotComputable("zero result")
    except (KeyError, TypeError) as e:
        raise NotComputable(str(e)) from None
    except NotComputable:
        raise

    q = s["retention"]
    out.update(leaching=y, discharge=y * (100 - q) * 0.01,
               pct_of_reference=y * (100 - q) * 0.01 * 100 / out["reference_discharge"],
               n_conc_mg_l=y * 100 / (summer + winter))
    return out


def compute(site, row, t: Tables):
    """One site and one crop row. Returns the output dict with a 'status' field."""
    try:
        s = _site(site, t)
    except (KeyError, TypeError) as e:
        return {"status": f"site not in tables: {e}"}
    try:
        return {"status": "ok", **compute_row(s, row, t)}
    except NotComputable as e:
        return {"status": f"not computable: {e}"}


def solve_mineral_n(site, row, t: Tables, target_discharge=None, upper=600.0, tol=0.01):
    """Spring mineral N (kg N/ha) that gives a target discharge to the coast.

    The workbook has no such calculation: it goes from N to leaching. This
    searches the other way, with everything else held fixed. target_discharge
    defaults to the spring-barley reference, the workbook's own yardstick. That
    is not a statutory quota: no quota is defined in the workbook.
    """
    def discharge(n):
        m = compute(site, {**row, "min_spring": n}, t)
        return m["discharge"] if m["status"] == "ok" else None

    low = compute(site, {**row, "min_spring": 0.0}, t)
    if low["status"] != "ok":
        return {"status": low["status"], "n_for_target": None, "target_discharge": target_discharge}
    if target_discharge is None:
        target_discharge = low["reference_discharge"]
    res = {"target_discharge": target_discharge, "discharge_at_zero_n": low["discharge"]}
    if low["discharge"] > target_discharge:
        return {**res, "status": "target unreachable: above target even at 0 kg", "n_for_target": 0.0}
    high = discharge(upper)
    if high is not None and high <= target_discharge:
        return {**res, "status": f"target not binding up to {upper:g} kg", "n_for_target": upper}
    a, b = 0.0, upper
    while b - a > tol:
        mid = (a + b) / 2
        d = discharge(mid)
        if d is not None and d <= target_discharge:
            a = mid
        else:
            b = mid
    return {**res, "status": "ok", "n_for_target": round(a, 2)}
