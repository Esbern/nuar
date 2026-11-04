# NUAR: what the SEGES spreadsheet does, and how to run it for points

Based on `NUAR-regneark (SEGES).xlsx`, version 1.3 (16 June 2026), read formula
by formula. The aim is to explain what the model needs and what it returns.

## In short

- **NUAR** is the new Danish nitrogen regulation from 2027. It regulates how
  much nitrogen a field discharges to the coast.
- **The calculation** ("NUAR-beregneren") is built on **NLES5**, Aarhus
  University's statistical model of nitrate leaching from the root zone. It is
  fitted to suction-cell measurements. AU has added measures that NLES5 lacks,
  and extended it to all crop codes.
- **The spreadsheet** is SEGES's preview of that calculation. SEGES states that
  the final data are not settled, and takes reservations for errors.

**The spreadsheet does not calculate how much fertiliser is allowed.** It runs
the other way: you give it crops and nitrogen, and it returns leaching and
discharge. The only "allowed amount" in it is the **N-norm**, which is a lookup
by crop and soil, not a result of the model. It also holds no quota. It compares
every field with a reference: spring barley with a catch crop on the same soil.

This project adds the missing direction: `--solve` finds the spring mineral N
that meets a target discharge. That is our own calculation, not part of the
spreadsheet, and the default target (the reference) is not a legal quota.

## The equation

Everything comes down to one line (sheet `Regn`, column EV):

```
Y = ( τ·(year − 1991) + (μ + θ·N + C)^1.5 · P · S · ρ ) · F_cover · F_maize · F_maize_grass
```

Then, per hectare:

```
discharge to coast = Y · (100 − retention %) / 100
```

| Term | Meaning | Depends on |
|---|---|---|
| Y | leaching from the root zone, kg N/ha | |
| τ·(year − 1991) | slow fall over time; τ = −0.11108 | harvest year |
| μ | intercept, 23.51 | |
| N | nitrogen effect, below | N inputs, soil N |
| θ | winter-crop class: 0, 1 or 1.205 | crop, winter cover |
| C | crop effect, sum of four table values | crop, previous crops, winter cover |
| P | drainage effect | runoff in three periods |
| S | clay effect, e^(0.001849 · clay %) | soil type |
| ρ | scaling factor, 1.085 | |
| F_cover | measures, below | catch crop, intermediate crop, early sowing, precision |
| F_maize | 0.72 for maize after a catch crop | crop, previous cover |
| F_maize_grass | a factor depending on spring mineral N, for maize after grass | crop, previous crop, N |

**The nitrogen effect N** adds up eight inputs:

| Input | Weight per kg N |
|---|---|
| mineral N, spring | 0.04957 |
| mineral N, autumn | 0.157044 |
| mineral N, grazing | 0.038245 |
| organic N in spring manure | 0.014099 |
| N fixation, harvest year | 0.016314 |
| N fixation, two previous years (mean) | 0.026499 |
| total N, two previous years (mean) | 0.026499 |
| total N in topsoil, per ton N/ha | 0.456793 |

Autumn mineral N weighs about three times as much as spring N. Organic N in manure
applied in autumn is not in the harvest-year term; it counts only through the
"previous years" term the year after.

**The drainage effect P:**

```
P = (1 − e^(−δ1·summer − δ2·winter)) · e^(−v2·winter_prev)
```

The δ and v values differ between "sandy" and "loamy". The sheet calls only
**JB 1 and 3** sandy, so JB 2 and JB 11 use the loamy values.

**The measures in F_cover.** Only one of the first three applies:

| Measure | Effect on leaching | Condition |
|---|---|---|
| catch crop | −45 % × a date factor | not for main-crop groups 4–7 |
| intermediate crop | −20 % | winter cereal category, crop allowed |
| early sowing of winter cereal | −20 % | winter cereal category |
| precision farming | −4 %, on top of the above | cereals and rape |

The date factor is 1.16 on 9 August or earlier, 1.00 on 20 August and 0.74 on
7 September, falling to 0 on 28 October. With no date, the sheet uses 20 August,
or 1 October for maize.

## What a point needs

Each row in the input is one point and one crop. Columns follow
[`examples/points_template.csv`](../examples/points_template.csv).

### The location (the same for all crops at a point)

| Column | Meaning | Values | Effect | Where to get it |
|---|---|---|---|---|
| `grid` | DMI 10 km climate grid | 10001–10609 | large: runoff, region | **needs a grid file**, see below |
| `jb` | soil class in the topsoil, 0–25 cm | 1–7, 11 | large | soil map |
| `c_horizon` | subsoil | Flyvesand, Litorina sand, Morænesand, Moræneler, Diluvialsand, Ferskvandssand, Yoldia sand | large: runoff | soil map |
| `lowland` | lowland class | blank, `Lavbund (minerogen)`, `Lavbund (organogen)` | large | lowland map |
| `irrigated` | irrigation, 0/1 | | changes the norm only | |
| `retention_pct` | N removed between root zone and coast | 0–100 | decides discharge | retention map |
| `year` | harvest year | default 2027 | small | |
| `manure_type` | type of manure | Svinegylle, Kvæggylle, Fjerkrægylle, Fjerkrægødning, Dybstrøelse, Biogasgylle, Anden organisk | sets the ammonium share | |

Region, JB class and subsoil combine into **Typejord**, which selects clay %,
soil N and the runoff.

**Only 56 Typejord values exist, so not every combination works.** Each region
has 9 mineral soil types, or 10 in Vestjylland, plus the two lowland classes.
JB 6 on moraine clay exists in Thy, Midtjylland and Østdanmark, but not in
Vestjylland or Nordjylland. Such a point returns blank in Excel and in the port.
Values taken from separate JB and subsoil maps will hit this. The planned AU
Typejord map should avoid it, but until it exists, the student has to decide how
to reassign those points.

| Region | Available JB group + subsoil codes |
|---|---|
| 1 Thy | 11, 18, 21, 24, 26, 46, 47, 48, 67 |
| 2 Nordjylland | 11, 14, 21, 24, 28, 44, 48, 211, 411 |
| 3 Vestjylland | 11, 12, 17, 18, 28, 37, 38, 47, 48, 110 |
| 4 Midtjylland | 16, 18, 27, 37, 38, 46, 47, 48, 67 |
| 5 Østdanmark | 16, 18, 37, 38, 46, 47, 48, 67, 77 |

Read a code as JB group, then subsoil number: 67 is JB group 6 on moraine clay
(7). JB 5 and 6 share group 6, JB 7–9 are group 7, and JB 2 and 11 are group 2.
Subsoil numbers: 1 Flyvesand, 2 Ferskvandssand, 4 Litorina sand, 6 Morænesand,
7 Moræneler, 8 Diluvialsand or Yoldia sand.

Three codes cannot be reached from the input cells: 211 and 411 use a subsoil 11
and 110 a subsoil 10, and the dropdown has neither. A note in the workbook says
Yoldia sand is really number 11 but is entered as 8.

**The climate grid is only a picture.** The workbook holds a map image with cell
numbers, with no coordinates. A point dataset needs the grid as a vector file,
or a georeferenced version of the picture, to find each point's `grid` number.
One label in the picture reads 0 where 10486 belongs. Bornholm is drawn as an
inset.

### The crops (three years, per point)

| Columns | Meaning |
|---|---|
| `crop`, `cover` | harvest year: main crop code and autumn–winter cover code |
| `prev_crop`, `prev_cover` | year before |
| `prev2_crop`, `prev2_cover` | two years before |

Crop codes are the standard Danish crop codes (324 listed, 282 computable). All
six columns must be filled: a missing previous crop or a missing previous cover
gives a blank result, except that `prev2_cover` may be blank. Cover codes
include 968 catch crop, 9680 N-fixing catch crop, 11 winter cereal, 22 winter
rape, 921 bare soil and 4000 weeds and volunteers.

Not every crop and cover pair is valid. 134 of 282 listed pairs are marked
`Ugyldig`, and they give a blank result.

### Measures (optional)

`catch_crop_date` (exact text, e.g. `20. aug.`), `early_sowing`,
`intermediate_crop`, `precision` (0/1), and `n_level_pct` (percentage of the
norm).

### Nitrogen, kg N/ha (optional, three years)

| Harvest year | Year before | Two years before | Meaning |
|---|---|---|---|
| `min_spring` | `prev_min_spring` | `prev2_min_spring` | mineral fertiliser, spring |
| `min_autumn` | `prev_min_autumn` | `prev2_min_autumn` | mineral fertiliser, after 1 August |
| `manure_spring` | `prev_manure_spring` | `prev2_manure_spring` | total N in manure, spring |
| `manure_autumn` | `prev_manure_autumn` | `prev2_manure_autumn` | total N in manure, after 1 August |
| `grazing` | `prev_grazing` | `prev2_grazing` | total N deposited by grazing |

### Optional overrides

`runoff_summer`, `runoff_winter`, `runoff_winter_prev` (mm) replace the table
values. `utilisation_pct` and `ammonium_pct` replace the manure defaults.

## What comes back

| Column | Meaning |
|---|---|
| `leaching` | Y, kg N/ha from the root zone |
| `discharge` | kg N/ha to the coast |
| `reference_discharge` | the same for spring barley with catch crop on this soil |
| `pct_of_reference` | discharge as a percentage of the reference |
| `n_norm` | the N-norm for the crop, after corrections |
| `n_conc_mg_l` | nitrate-N in root-zone water |
| `n_fixation` | calculated N fixation |
| `runoff_summer`, `runoff_winter`, `runoff_winter_prev` | runoff used, mm (`out_` prefix when the input has these columns) |
| `status` | `ok`, or why there is no result |
| `n_for_target`, `solve_status` | with `--solve`: the spring mineral N that meets the target |

`--solve` holds everything else fixed. If the field is above the target even at
0 kg, it returns 0 and says so. For B and C in the template that is the case:
the crop, cover and history matter more than the fertiliser.

## Traps

1. **Blank is not zero.** A blank `min_spring` means "apply the norm". It is
   then added to any manure, so a field with 170 kg manure N and a blank
   `min_spring` gets the full norm as well. Enter 0 for no mineral fertiliser.
   The same applies to `min_autumn` and to both previous years.
2. **Fertiliser in the previous years defaults to the norm too.** Without real
   records, you are modelling a field fertilised at the norm.
3. **`n_level_pct` scales the norm only.** It has no effect when `min_spring`
   is filled in.
4. **The reference is not an ordinary row.** It assumes spring barley for two
   previous years, at the norm minus 21 in both. A row entered as spring barley
   three years running comes out at about 101 %, because the sheet applies the
   norm for two years before without the catch-crop deduction.

## Possible errors in the workbook

For SEGES to confirm. The port reproduces all of these on purpose, so that it
stays comparable with the spreadsheet.

1. **The ammonium override does not reach the organic share (confirmed in
   Excel).** Mineral N uses the override in `L11`, but organic N uses `I11`,
   which ignores it. With `Anden organisk` at 40 % ammonium, 100 kg N becomes
   40 mineral + 100 organic = 140 kg. With Svinegylle overridden to 40 %, it
   becomes 40 + 25 = 65 kg. This is the case the sheet's own note tells users
   to enter. The CLI prints a warning when `ammonium_pct` is used.
2. **The validity column for previous covers is not used.** `Vpldkat2` marks 309
   of 540 combinations `Ugyldig` in column 8, but the formula reads column 7, so
   they calculate as normal. This may be deliberate.
3. **Pasted examples no longer reproduce.** The hidden sheet
   `Tabel Kvælstofudvaskning` holds worked examples as values. Of 339 examples
   whose inputs could be reconstructed, current Excel gives a different result
   for 290. They may stem from an older version, or from inputs that were not
   recorded. They are not used as a test.

## How it was checked

The real workbook, run in real Excel, is the reference. Random scenarios go
through both Excel and the port, and every output is compared.

| Test set | Rows | Numeric in both | Blank in both | Disagree on blank | Numeric mismatches |
|---|---|---:|---:|---:|---:|
| Random, first run | 1,000 | 251 | 749 | 0 | 0 |
| Random, realistic sites and rotations | 7,500 | 4,040 | 3,460 | 0 | 0 |
| Targeted at measures and maize factors | 2,000 | 1,835 | 165 | 0 | 0 |
| **Total** | **10,500** | **6,126** | **4,374** | **0** | **0** |

The largest difference in leaching was 3.4 × 10⁻¹³ kg N/ha. All 22 output columns
were compared, with a tolerance of one part in a million.

The rows reached the branches that matter:
- winter cereals with early sowing, intermediate crop and precision farming
  (369 rows with an effect);
- maize after a catch crop (153 rows at the 0.72 factor in the targeted set);
- maize after grass, on both sides of the 80 kg threshold (490 rows);
- `Anden organisk`, ammonium overrides, lowland, grazing and runoff overrides.

Not tested: real field data, as none was in the folder. All rows are generated
scenarios. Blank results show that both engines refuse the same inputs, not that
the refusal is sensible.

The port is a snapshot of version 1.3. SEGES will update the workbook as the
data settle (runoff map, soil data, crop categories). The CLI warns on a new
version. Rerun `tests/compare.py` before trusting the port on it, and the Excel
engine will keep working in the meantime as long as the input cells stay put.

## Before this is used in a thesis or in publications

- Cite the AU reports listed in the workbook, not this code.
- This reads a preliminary tool. State the version and that the final
  regulation may differ.
- The workbook is SEGES's. Its tables stay out of this repository (`data/` is
  git-ignored). Ask SEGES before sharing the port, as it reproduces their
  formulas.
