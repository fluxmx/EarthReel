from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from earthreel.config import DataConfig


@pytest.fixture
def dataset(tmp_path):
    def create(*, lat=None, lon=None, values=None, units="K", extra=False):
        lat = np.array([90, 45, 0, -45, -90] if lat is None else lat, dtype=float)
        lon = np.array([-180, -90, 0, 90] if lon is None else lon, dtype=float)
        if values is None:
            values = 273.15 + lat[:, None] / 10 + np.cos(np.deg2rad(lon))[None, :]
        values = np.asarray(values, dtype=float)[None]
        dims = ("valid_time", "latitude", "longitude")
        if extra:
            dims = ("level", *dims)
            values = values[None]
        ds = xr.Dataset(
            {"t2m": (dims, values, {"units": units})},
            coords={
                "valid_time": np.array(["2000-01-01T00:00"], dtype="datetime64[ns]"),
                "latitude": lat,
                "longitude": lon,
            },
        )
        path = tmp_path / "input.nc"
        ds.to_netcdf(path, engine="netcdf4")
        return DataConfig(path)

    return create


@pytest.fixture
def example_path():
    return Path(__file__).resolve().parents[1] / "examples" / "era5_t2m.yml"
