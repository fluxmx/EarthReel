# Copyright 2026 fluxmx
# SPDX-License-Identifier: Apache-2.0
"""Read global regular-grid temperature or velocity fields without resampling."""

from dataclasses import dataclass

import numpy as np
import xarray as xr

from earthreel.config import DataConfig


@dataclass(frozen=True)
class ScalarField:
    latitude: np.ndarray
    longitude: np.ndarray
    values: np.ndarray
    time_utc: str
    original_units: str
    long_name: str
    display_units: str


@dataclass(frozen=True)
class TemperatureField:
    latitude: np.ndarray
    longitude: np.ndarray
    celsius: np.ndarray
    time_utc: str
    original_units: str
    long_name: str = "2 metre temperature"

    @property
    def values(self) -> np.ndarray:
        return self.celsius

    @property
    def display_units(self) -> str:
        return "°C"


def _open_field_dataset(config: DataConfig) -> xr.Dataset:
    """Select only the requested GRIB variable before building a cfgrib hypercube."""
    with config.path.open("rb") as stream:
        is_grib = stream.read(4) == b"GRIB"
    if not is_grib:
        return xr.open_dataset(config.path, engine="netcdf4", decode_cf=True)
    try:
        import cfgrib  # noqa: F401
    except ImportError as error:
        raise RuntimeError("GRIB input requires: python -m pip install -e '.[grib]'") from error
    return xr.open_dataset(
        config.path,
        engine="cfgrib",
        backend_kwargs={
            "filter_by_keys": {"cfVarName": config.variable},
            "indexpath": "",  # Do not create sidecar indexes beside source data.
            "errors": "raise",
        },
    )


def load_field(config: DataConfig) -> ScalarField:
    if type(config.time_index) is not int or config.time_index < 0:
        raise ValueError("time_index must be a non-negative integer")
    with _open_field_dataset(config) as ds:
        for name in (config.variable, config.latitude, config.longitude, config.time):
            if name not in ds:
                raise ValueError(f"Variable or coordinate {name!r} not found in {config.path.name}")
        array = ds[config.variable]
        lat, lon, time = ds[config.latitude], ds[config.longitude], ds[config.time]
        if lat.ndim != 1 or lon.ndim != 1 or time.ndim not in (0, 1):
            raise ValueError("Only one-dimensional latitude/longitude and scalar or 1D time are supported")
        lat_dim, lon_dim = lat.dims[0], lon.dims[0]
        if lat_dim == lon_dim or (time.ndim and time.dims[0] in (lat_dim, lon_dim)):
            raise ValueError("Latitude, longitude and time must have distinct dimensions")
        expected_dims = {lat_dim, lon_dim, *time.dims}
        if set(array.dims) != expected_dims:
            raise ValueError("Field must have only time, latitude and longitude dimensions")
        if config.time_index >= time.size:
            raise ValueError(
                f"time_index {config.time_index} out of range; choose 0..{time.size - 1}"
            )
        selected = array.isel({time.dims[0]: config.time_index}) if time.ndim else array
        selected = selected.transpose(lat_dim, lon_dim)
        units = str(array.attrs.get("units", "")).strip()
        long_name = str(array.attrs.get("long_name", config.variable))
        values = np.asarray(selected.values, dtype=np.float64)
        display_units = "°C"
        if units.lower() in {"k", "kelvin"}:
            values = values - 273.15
        elif units in {"m s**-1", "m s-1", "m/s", "m s^-1"}:
            display_units = "m/s"
        elif units.lower() not in {
            "°c",
            "degc",
            "c",
            "celsius",
            "degree_celsius",
            "degrees_celsius",
        }:
            raise ValueError(
                f"Unsupported field units {units!r}; expected K, degrees Celsius or m/s"
            )
        values[~np.isfinite(values)] = np.nan
        latitudes = np.asarray(lat.values, dtype=float)
        longitudes = np.asarray(lon.values, dtype=float)
        stamp = time.values[config.time_index] if time.ndim else time.values[()]
        if not np.issubdtype(time.dtype, np.datetime64) or np.isnat(stamp):
            raise ValueError("Time must decode to a valid Gregorian datetime")
        time_utc = np.datetime_as_string(stamp, unit="s") + "Z"

    if not np.isfinite(latitudes).all() or not np.isfinite(longitudes).all():
        raise ValueError("Coordinates must contain only finite values")
    if latitudes.size < 3 or longitudes.size < 4:
        raise ValueError("Global grid needs at least 3 latitude rows and 4 longitude columns")
    if (np.abs(latitudes) > 90 + 1e-7).any():
        raise ValueError("Latitude must be within -90..90 degrees")
    lat_order = np.argsort(latitudes)
    longitudes = np.mod(longitudes, 360)
    lon_order = np.argsort(longitudes, kind="stable")
    latitudes, longitudes = latitudes[lat_order], longitudes[lon_order]
    values = values[np.ix_(lat_order, lon_order)]

    # Only an equivalent cyclic endpoint may repeat; never silently discard conflicts.
    duplicate = np.flatnonzero(np.isclose(np.diff(longitudes), 0, atol=1e-7))
    if duplicate.size:
        if duplicate.size != 1:
            raise ValueError("Longitude has multiple duplicate coordinates")
        i = duplicate[0]
        if not np.allclose(values[:, i], values[:, i + 1], equal_nan=True):
            raise ValueError("Duplicate cyclic longitude has conflicting values")
        longitudes = np.delete(longitudes, i + 1)
        values = np.delete(values, i + 1, axis=1)

    dlat = np.diff(latitudes)
    dlon = np.diff(np.r_[longitudes, longitudes[0] + 360])
    if (dlat <= 0).any() or not np.allclose(dlat, dlat[0], rtol=1e-5, atol=1e-7):
        raise ValueError("Latitude must form a regular grid without duplicates")
    if (dlon <= 0).any() or not np.allclose(dlon, dlon[0], rtol=1e-5, atol=1e-7):
        raise ValueError("Longitude must form a regular global grid covering 360 degrees")
    if latitudes[0] > -90 + dlat[0] / 2 + 1e-7 or latitudes[-1] < 90 - dlat[0] / 2 - 1e-7:
        raise ValueError("Latitude must cover the globe, including both polar regions")
    if not np.isfinite(values).any():
        raise ValueError("Selected field has no valid values")
    return ScalarField(latitudes, longitudes, values, time_utc, units, long_name, display_units)


def load_temperature(config: DataConfig) -> TemperatureField:
    """Compatibility entry point for callers that explicitly require temperature."""
    field = load_field(config)
    if field.display_units != "°C":
        raise ValueError(f"Unsupported temperature units {field.original_units!r}")
    return TemperatureField(
        field.latitude, field.longitude, field.values, field.time_utc,
        field.original_units, field.long_name,
    )
