"""Exercise real multi-variable GRIB decoding without downloading test data."""

from dataclasses import replace

import numpy as np
import pytest

from earthreel.config import DataConfig
from earthreel.data import load_field, load_temperature


def test_grib_selects_t2m_and_valid_time(tmp_path):
    ec = pytest.importorskip("eccodes")
    path = tmp_path / "surface.grib2"
    temperatures = np.arange(20, dtype=float) + 260
    with path.open("wb") as stream:
        for short_name in ("2t", "10u", "sve", "svn"):
            handle = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")
            try:
                for key, value in {
                    "centre": "ecmf",
                    "Ni": 4,
                    "Nj": 5,
                    "latitudeOfFirstGridPointInDegrees": 90,
                    "latitudeOfLastGridPointInDegrees": -90,
                    "longitudeOfFirstGridPointInDegrees": 0,
                    "longitudeOfLastGridPointInDegrees": 270,
                    "iDirectionIncrementInDegrees": 90,
                    "jDirectionIncrementInDegrees": 45,
                    "dataDate": 20261030,
                    "dataTime": 1800,
                    "step": 3,
                    "shortName": short_name,
                }.items():
                    ec.codes_set(handle, key, value)
                values = temperatures if short_name == "2t" else np.linspace(-1, 1, 20)
                if short_name in ("sve", "svn"):
                    ec.codes_set(handle, "bitmapPresent", 1)
                    values[0] = ec.codes_get(handle, "missingValue")
                ec.codes_set_values(handle, values)
                ec.codes_write(handle, stream)
            finally:
                ec.codes_release(handle)
    config = DataConfig(path)
    field = load_temperature(config)
    assert field.time_utc == "2026-10-30T21:00:00Z"
    assert field.original_units == "K"
    np.testing.assert_allclose(field.celsius, temperatures.reshape(5, 4)[::-1] - 273.15)
    assert not list(tmp_path.glob("*.idx"))
    with pytest.raises(ValueError, match="out of range"):
        load_temperature(replace(config, time_index=1))
    with pytest.raises(ValueError, match="not found"):
        load_temperature(replace(config, variable="missing"))

    for variable in ("sve", "svn"):
        velocity_config = replace(config, variable=variable)
        velocity = load_field(velocity_config)
        expected = np.linspace(-1, 1, 20).reshape(5, 4)[::-1].copy()
        expected[-1, 0] = np.nan
        np.testing.assert_allclose(velocity.values, expected, atol=1e-6)
        assert velocity.display_units == "m/s"
        assert velocity.time_utc == "2026-10-30T21:00:00Z"
        with pytest.raises(ValueError, match="temperature units"):
            load_temperature(velocity_config)
