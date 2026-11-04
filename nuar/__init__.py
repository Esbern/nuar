import os as _os

# The mamba env this project uses (see README) ships its own PROJ data under
# share/proj, but geopandas/pyproj don't always find it automatically, which
# silently breaks CRS transforms (every point ends up unmatched, no error).
# Point at it unless the environment already sets PROJ_DATA itself.
if "PROJ_DATA" not in _os.environ:
    import sysconfig as _sc

    _candidate = _os.path.join(_sc.get_config_var("base") or "", "share", "proj")
    if _os.path.exists(_os.path.join(_candidate, "proj.db")):
        _os.environ["PROJ_DATA"] = _candidate
