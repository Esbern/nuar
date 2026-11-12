"""The exported tables (export-tables) must be exactly the workbook's tables.

  NUAR_WORKBOOK=<workbook> python -m pytest tests/test_tables_export.py
"""
import os
from pathlib import Path

import pytest

from nuar import tables

WB = os.environ.get("NUAR_WORKBOOK")


@pytest.mark.skipif(not WB or not Path(WB).exists(), reason="set NUAR_WORKBOOK to the SEGES workbook")
def test_export_round_trip(tmp_path):
    t = tables.build(Path(WB))
    tables.export(t, tmp_path)
    u = tables.load(tmp_path)
    assert u.version == t.version
    assert u.tab == t.tab
    assert (u.par, u.konst, u.grid_ids, u.crop_name, u.cover_name) == (t.par, t.konst, t.grid_ids, t.crop_name, t.cover_name)
