# Data to acquire for processing points

What to get for each NUAR input, where to look, and what's uncertain. Checked
by web search on 4 Nov 2026; portals and dataset names change, so confirm
before relying on anything here. **Retention** is now a verified, working
pipeline (fetched, joined and run through the model end to end); the other
five inputs are still unconfirmed leads, not a tested pipeline.

## Summary

| NUAR input | Dataset | Likely source | Confidence |
|---|---|---|---|
| `retention_pct` | Kvælstofretention UMR 2027 | **found** — `geodata.fvm.dk`, public WFS, no login | confirmed |
| `jb`, soil class 0–25 cm | Jordbundstypekort (Tekstur2014 or a newer version) | Danmarks Miljøportal / Landbrugsstyrelsen | low–medium |
| `c_horizon`, subsoil | Danmarks digitale jordartskort | GEUS | medium |
| `lowland` | Lavbundskort | Danmarks Miljøportal (MiljøGIS, layer "Kulstof 2022" or DJF_LAVBUND) | medium |
| `grid`, DMI climate grid | Climate Grid Denmark | DMI | low, but **low-stakes** — see below |
| `crop`, `cover` | Markblokke + Fællesskema afgrødekort | Landbrugsstyrelsen (now under SGAV) | medium |

None of these are confirmed as bulk, no-login downloads. Treat every link
below as a starting point to check, not a working URL.

## Retention — found and wired in

`retention_pct` is the one NUAR input the workbook cannot supply itself: the
spreadsheet doesn't calculate it, it only uses whatever number you give it
(`I5` in `NUAR-regneark`) to scale leaching down to discharge at the coast.
Without a real value it's silently wrong, not blank — a missing retention
reads as 0, i.e. full discharge, with no error.

**Esbern found the right layer:** the official UMR retention map, served live
and with no login needed:

```
URL:   https://geodata.fvm.dk/geoserver/ows
Layer: Udledningsbaseret_mark_regulering:Kvaelstofretention_UMR_2027
```

Confirmed by fetching it directly (4 Nov 2026):

- **96,377 polygons**, EPSG:25832, each with `RetTot` (retention %, 0–100) and
  `KystvandID` (the coastal-water catchment it belongs to).
- **Not field-resolution.** The finest polygon is one 100×100 m grid cell,
  but most are much larger — up to ~80 km² in a sample check, and only about
  10 distinct `RetTot` values turned up in 500 features. Retention is modelled
  per catchment / catchment sub-area and is piecewise constant across it, not
  a smoothly varying surface. Don't expect it to distinguish two points on
  the same farm.
- No API key, no rate limit hit during testing.

**This project now fetches it automatically.** `nuar/retention.py` wraps the
WFS call and a `geopandas.sjoin`; the CLI exposes it as
`--fetch-retention`, which needs point geometry (an `x`/`y` column pair in a
csv, EPSG:25832 or lon/lat, or a gpkg/shp/geo-parquet input):

```bash
mamba run -n nuar python -m nuar run points.csv -o result.csv --fetch-retention
```

A point exactly on a 100 m cell edge, or outside the layer (open water, just
past the coast), comes back with no retention value; the CLI warns with a
count when that happens.

## Soil class (JB number, topsoil 0–25 cm)

NUAR wants JB 1, 2, 3, 4, 5, 6, 7 or 11 (see
[NUAR_explained.md](NUAR_explained.md)).

- The Danish JB classification has been remapped at least twice: **Tekstur2014**
  (Aarhus University, from soil texture and organic carbon) was the original
  basis; a newer **Tekstur2024** is referenced in a 2024 ministry note
  ([miljoeportal.dk PDF](https://miljoeportal.dk/media/2039/opdateret_jordbundstypekort_1903_2024.pdf)).
  A farming-press article reports more detailed soil-type and texture maps
  becoming available: [landbrugsavisen.dk](https://landbrugsavisen.dk/mark/nu-kan-du-se-mere-detaljerede-kort-over-jordtype-og-tekstur).
- One official note states Tekstur2014 "kan ikke alene anvendes til
  prioritering af arealer" (should not be used alone to prioritise land) —
  worth keeping in mind if accuracy at the field level matters for the thesis.
- A hosted layer, "Jordbundskort_2019" from Landbrugsstyrelsen, appears on a
  Vejdirektoratet map server: [kort.vd.dk/.../Jordbundskort_2019](https://kort.vd.dk/server/rest/services/Grunddata/Jordbundskort_2019/MapServer/layers).
  That's a REST map service (viewable, maybe queryable), not necessarily a
  bulk download, and it's a third party re-hosting the data, so check whether
  it matches the authoritative source before using it.

**Open question: which version NUAR expects.** The spreadsheet just says "JB
nr. for overjorden" with no version reference. Tekstur2014 is the one the JB
system itself is historically tied to; a newer map might reclassify some
fields. Worth confirming with SEGES or AU directly, since this choice changes
which Typejord combinations are even reachable (see the soil-combination table
in NUAR_explained.md).

## Subsoil (C-horisont)

NUAR's dropdown options are Flyvesand, Litorina sand, Morænesand, Moræneler,
Diluvialsand, Ferskvandssand, Yoldia sand — geological, not agronomic, classes.

- **Danmarks digitale jordartskort**, GEUS, 1:25,000, is free via GEUS's web
  shop / Danmarks Geologiportal. Latest versions found: 6.0 (2021) and 7.0
  (2023). See [pub.geus.dk, v6.0](https://pub.geus.dk/en/publications/danmarks-digitale-jordartskort-125000-version-60/)
  and the GEUS Geonetwork record:
  [data.geus.dk/geonetwork/.../71d1d132...](https://data.geus.dk/geonetwork/srv/api/records/71d1d132-d6d2-4f02-9063-31a495e05b1d).
- It maps the deposit at roughly 1 m depth, close to but not confirmed
  identical to "C-horizon" in NUAR's sense — check the legend/attribute
  documentation before assuming the match.
- "Diluvialsand" is an older term; current map legends may use different
  category names (e.g. smeltevandssand). A lookup from the current legend's
  categories to NUAR's seven dropdown values will likely be needed by hand —
  this is the kind of table worth confirming with SEGES, since the workbook's
  own comment (`Normer!E206`) already flags one of its own codes as wrong
  ("det rigtige nr. 11, men er indtastet som 8").

## Lowland (Lavbund)

- Access point: **MiljøGIS**, reached via `mst.dk/lavbund`. The guidance names
  a layer "Kulstof 2022 (lavbundskort)" used for project prioritisation:
  [mst.dk vejledning PDF](https://mst.dk/media/qzscysi0/vejledning-til-ansoegning-og-projektgennemfoersel-klima-lavbund-v-2024.pdf).
- A map-service layer "DJF_LAVBUND" ("Lavbund og Okker") is listed on
  [kort.vd.dk/.../Grunddata/Jordbund_og_terræn](https://kort.vd.dk/server/rest/services/Grunddata/Jordbund_og_terr%C3%A6n/MapServer/layers).
- Broader access: **Danmarks Miljøportal's Arealdata/Danmarks Arealinformation**
  system claims over 1,000 datasets and WMS/WFS/WMTS services, including soil
  type and land use: [miljoeportal.dk/arealdata](https://miljoeportal.dk/en/danmarks-miljoeportal-s-systems/arealdata),
  [Danmarks Arealinformation](https://miljoeportal.dk/en/danmarks-miljoeportal-s-systems/danmarks-arealinformation).
  This portal is probably the single best place to check first for lowland,
  soil type and possibly subsoil layers together, since they're run by the
  same organisation.

**Confirm:** whether this layer distinguishes minerogen vs. organogen lowland,
since NUAR needs that split, not just "lowland yes/no".

## Climate grid

- **No shapefile download was confirmed.** DMI's Klimaatlas is on Zenodo as a
  1 km GeoTIFF/NetCDF grid: [Zenodo v2025a](https://zenodo.org/records/17491764).
  That is NUAR's climate PCA input grid (the one you already use via
  `~/dev/klimaatlas-climate-pca`), but it's **1 km**, not the 10 km
  `grid` field NUAR's `NUAR-regneark!D5` wants.
- NUAR's own 10 km grid is documented in DMI's "Climate Grid Denmark"
  technical report: [dmi.dk/.../tr12-10.pdf](https://www.dmi.dk/fileadmin/Rapporter/TR/tr12-10.pdf).
  It describes 609 cells (IDs 10001–10609, matching the workbook's `GridTab`
  exactly) plus 178 20×20 km cells. The report states non-commercial
  research/educational use only — check whether that covers a thesis, and
  whether redistribution (e.g. committing cell geometry to this repo) is
  allowed.
- An R package, `dmir` ([manual](https://ldalby.r-universe.dev/dmir/doc/manual.html)),
  ships a `grid_10km` dataset described as "Det Danske Kvadratnet" at 10 km,
  and a `dmi_get_grid()` function (needs a DMI API key). This is the most
  promising lead for actual cell geometry — worth checking even though it's R,
  not Python; the shapefile/data object itself could be reused directly.

**This is still the weakest-confirmed item**, but it matters much less than it
looks like it should — measured directly against the Python port, not
guessed. In the formulas, `grid` feeds exactly two things:

1. **Georegion** (1 of 5: Thy, Nordjylland, Vestjylland, Midtjylland,
   Østdanmark) → part of `Typejord` → the topsoil total-N and clay %
   defaults (`SoilidTab`).
2. **Default drainage/percolation** for two periods, looked up from `AfstrDat`
   (609 grids × ~56 soil types × 8 crop drainage classes).

I tested both effects by holding soil and crop fixed (JB 6, moraine clay,
spring barley with a catch crop, 125 kg N) and varying only `grid`, across all
609 grid cells, using the Python port:

| What varies | Leaching range | Spread (stdev) |
|---|---|---|
| Everything `grid` touches (region + default runoff) | 14.1 – 36.9 kg N/ha | 4.65 |
| Only the region effect (runoff pinned to one fixed value via `runoff_summer`/`runoff_winter`/`runoff_winter_prev`) | 27.1 – 28.3 kg N/ha | **0.35** |

**Getting the region right barely matters (≈1 % of leaching) — getting
runoff right is almost the whole effect of `grid`.** So the DMI 10 km grid ID
itself isn't really the thing worth chasing; real local drainage/percolation
estimates are.

**On reusing the signatur climate-PCA data (`~/dev/klimaatlas-climate-pca`,
`/mnt/d/klimanormal`) for this:** it's a *different* DMI product — "Klimaatlas"
model climatology at 1 km (RCP4.5, bias-corrected, 1981–2010), not the
"Climate Grid Denmark" 10 km grid NUAR's `D5` expects — so there's no ready ID
crosswalk between them. But it does carry seasonal precipitation and potential
evaporation (Makkink), which is in principle what drainage is built from.
**Don't substitute it directly**, though: `AfstrDat`'s columns are
`Perc_Apri_aug_mm` / `Perc_sept_mar_mm` — the *output* of AU's own calibrated
percolation/water-balance model (soil-aware, already net of real
evapotranspiration), not raw precipitation minus potential ET. A DIY
precip-minus-PET estimate from klimanormal would be a materially different,
unvalidated method standing in for a calibrated one, and the period split
(Apr–Aug / Sep–Mar) doesn't line up with klimanormal's seasons (DJF/MAM/JJA/SON)
either, so there's re-aggregation to do either way.

**What I'd actually do:** since the region effect is small, don't spend time
reconstructing the DMI 10 km grid precisely — a rough Georegion assignment
(even picking the right one of 5 regions by eye from a Denmark map) is good
enough, confirmed above at ≈1 % of leaching. If better drainage data than
`AfstrDat`'s lookup becomes available later (e.g. from AU directly, not
reverse-engineered from klimanormal), feed it straight in via
`runoff_summer`/`runoff_winter`/`runoff_winter_prev`, which the CLI already
passes through as overrides — no grid or region needed to use them.

## Crops (markblok + afgrøde)

- **Markblokke** (field blocks, ~450,000 polygons): managed by Landbrugsstyrelsen
  (now partly under Styrelsen for Grøn Arealomlægning og Vandmiljø, SGAV).
  Polygons update at least every 3 years; related services update daily. An
  EU INSPIRE record lists a WFS endpoint, but on a third-party host
  (haleconnect.com) — verify against the agency's own page before trusting it:
  [INSPIRE record](https://inspire-geoportal.ec.europa.eu/srv/api/records/96bf2cc2-53a8-4370-ba3a-d67b24a0f129).
- **Afgrødekort** (actual declared crop per field, from Fællesskema): a 2026
  summary PDF exists: [lbst.dk Afgrødefordeling 2026](https://lbst.dk/Media/639184876540682934/Opgørelse%20af%20ansøgningsrunden%20til%20fællesskema%202026%20-%20Afgrødefordeling.pdf)
  — aggregate statistics, not a field-level download, but confirms the
  current agency and year's reporting exists.
- **A usable open copy may already exist**, prepared from the Danish
  Agriculture Agency's own data: [Fieldscapes Denmark on source.coop](https://source.coop/kerner-lab/fieldscapes-denmark).
  Worth checking first — it could save re-deriving the WFS access yourself.
- **Crop code matching:** NUAR's `TabAfgrnr` already uses what look like the
  standard Danish "afgrødekode" values (the same codes Fællesskema uses), so
  a crosswalk may not even be needed — check a handful of codes from the
  afgrødekort against `t.crop_name` in `nuar/tables.py` to confirm before
  assuming it.
- The authoritative portal for both layers is **dataforsyningen.dk** — my
  search didn't surface its exact catalogue page or WFS URL, so check there
  directly.

## Suggested order of attack

1. **Retention — done.** `--fetch-retention` fetches and joins it live; no
   further acquisition needed.
2. **Markblokke + afgrødekort** next — this fixes which points exist and
   what `crop`/`cover` sequences are real, before spending time on the other
   layers for points that might not matter.
3. **Soil (JB), subsoil and lowland** together, since Danmarks Miljøportal's
   Arealdata looks likely to host all three.
4. **Climate grid last, and don't over-invest in it.** The sensitivity check
   above shows the region it determines barely moves leaching (≈1 %); a rough
   assignment is enough unless you also get real drainage/percolation data to
   feed in via the runoff overrides.

Once each layer is actually in hand (format, attribute names, projection),
I can help write the join from point geometry to each required NUAR column —
that part should be straightforward once the sources are confirmed.
