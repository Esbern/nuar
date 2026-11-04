# dkn_10km.geojson

Fetched 2026-11-04 from the DMI Climate Data Grid Map project, DMI's own
GitHub organisation:

```
https://raw.githubusercontent.com/dmidk/Climate-Data-Grid-Map/main/10x10/10x10.geojson
```

609 features (matches NUAR's `GridTab` cell count exactly), EPSG:4326, one
`cellId` per polygon in DKN's own naming (`10km_<northing/10km>_<easting/10km>`,
ETRS89 / DKN_10km_ETRS89, per
https://www.dmi.dk/friedata/dokumentation/climate-data). Published by DMI for
import into QGIS; see `nuar/grid.py` for how NUAR's own sequential grid IDs
(10001–10609) are derived from it.

Re-included here as a small (145 KB), DMI-published, publicly hosted file.
Check DMI's own terms before further redistribution if that matters for your
use.
