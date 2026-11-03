import hashlib
from dataclasses import replace

import numpy as np
import pytest
import xarray as xr

from earthreel.config import load_config
from earthreel.data import load_temperature
from earthreel.render import cell_globe_mesh, globe_mesh, temperature_lut


def test_nearest_cells_preserve_samples_and_missing(dataset):
    values = np.arange(20, dtype=float).reshape(5, 4)
    values[1, 1] = np.nan
    field = load_temperature(dataset(values=values, units="degrees_Celsius"))
    mesh = cell_globe_mesh(field)
    assert mesh.n_cells == field.celsius.size
    assert mesh.n_open_edges == 0
    assert "scalar_value" not in mesh.point_data
    scalars = mesh.cell_data["scalar_value"]
    assert np.isnan(scalars).sum() == 1
    np.testing.assert_array_equal(
        np.sort(scalars[np.isfinite(scalars)]), np.sort(values[np.isfinite(values)])
    )
    assert scalars[mesh.find_closest_cell([1, 0, 0])] == field.celsius[2, 0]


def test_freezing_point_colour_mapping(example_path):
    config = load_config(example_path)
    table = temperature_lut(config)
    cold, neutral, warm = [0.0] * 3, [0.0] * 3, [0.0] * 3
    table.GetColor(-5, cold)
    table.GetColor(0, neutral)
    table.GetColor(5, warm)
    assert cold[2] > cold[0]
    assert warm[0] > warm[2]
    assert max(neutral) - min(neutral) < 0.025
    assert table.scalar_range == (-60, 40)


def test_coordinates_values_and_missing(dataset):
    values = np.arange(20, dtype=float).reshape(5, 4) + 273.15
    values[2, 2] = np.nan
    field = load_temperature(dataset(values=values))
    np.testing.assert_array_equal(field.latitude, [-90, -45, 0, 45, 90])
    np.testing.assert_array_equal(field.longitude, [0, 90, 180, 270])
    np.testing.assert_allclose(field.celsius, (values - 273.15)[::-1, [2, 3, 0, 1]])
    assert np.isnan(field.celsius[2, 0])
    assert field.time_utc == "2000-01-01T00:00:00Z"


def test_celsius_is_not_converted_again(dataset):
    field = load_temperature(dataset(values=np.zeros((5, 4)), units="degrees_Celsius"))
    assert np.all(field.celsius == 0)


def test_transposed_dimensions(dataset):
    config = dataset()
    with xr.open_dataset(config.path) as ds:
        changed = ds.load().transpose("longitude", "valid_time", "latitude")
    changed.to_netcdf(config.path, engine="netcdf4")
    field = load_temperature(config)
    assert field.celsius.shape == (5, 4)
    assert field.celsius[2, 0] == pytest.approx(1)


def test_equivalent_cyclic_endpoint(dataset):
    config = dataset(lon=[0, 90, 180, 270, 360])
    field = load_temperature(config)
    assert field.celsius.shape == (5, 4)
    values = np.zeros((5, 5))
    values[:, -1] = 1
    with pytest.raises(ValueError, match="conflicting"):
        load_temperature(dataset(lon=[0, 90, 180, 270, 360], values=values))


@pytest.mark.parametrize(
    "kind,match",
    [
        ("unit", "units"),
        ("variable", "not found"),
        ("time", "out of range"),
        ("negative", "non-negative"),
        ("regional", "global"),
        ("extra", "dimensions"),
        ("missing", "no valid"),
        ("latitude", "regular"),
    ],
)
def test_invalid_inputs(dataset, kind, match):
    options = {}
    if kind == "unit":
        options["units"] = "Fahrenheit"
    elif kind == "regional":
        options["lon"] = [0, 10, 20, 30]
    elif kind == "extra":
        options["extra"] = True
    elif kind == "missing":
        options["values"] = np.full((5, 4), np.nan)
    elif kind == "latitude":
        options["lat"] = [-90, -30, 0, 45, 90]
    config = dataset(**options)
    if kind == "variable":
        config = replace(config, variable="bad_name")
    elif kind == "time":
        config = replace(config, time_index=3)
    elif kind == "negative":
        config = replace(config, time_index=-1)
    with pytest.raises(ValueError, match=match):
        load_temperature(config)


def test_closed_globe_geometry_and_scalar_location(dataset):
    field = load_temperature(dataset())
    mesh = globe_mesh(field)
    assert mesh.n_open_edges == 0
    np.testing.assert_allclose(np.linalg.norm(mesh.points, axis=1), 1)
    # Equator / Greenwich is +X; 90E is +Y; north is +Z.
    for point, expected in (([1, 0, 0], 1), ([0, 1, 0], 0), ([0, 0, 1], 9)):
        index = mesh.find_closest_point(point)
        np.testing.assert_allclose(mesh.points[index], point, atol=1e-12)
        assert mesh["scalar_value"][index] == pytest.approx(expected)
    triangles = mesh.triangulate()
    cells = triangles.faces.reshape(-1, 4)[:, 1:]
    a, b, c = (triangles.points[cells[:, i]] for i in range(3))
    normals = np.cross(b - a, c - a)
    assert np.all(np.sum(normals * (a + b + c), axis=1) > 0)


def test_polar_missing_is_not_filled(dataset):
    values = np.zeros((5, 4))
    values[0, 0] = np.nan
    field = load_temperature(dataset(values=values))
    mesh = globe_mesh(field)
    assert np.isnan(mesh["scalar_value"][mesh.find_closest_point([0, 0, 1])])


def test_bundled_era5_all_times(example_path):
    config = load_config(example_path).data
    with config.path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == (
            "1446569402ff1142f2a96988d2eeb6ca4ca9cb7c98d2d288878152cd2f3d6e2a"
        )
    with xr.open_dataset(config.path) as ds:
        for index in range(3):
            field = load_temperature(replace(config, time_index=index))
            assert field.celsius.shape == (721, 1440)
            assert field.time_utc == f"2000-01-01T0{index}:00:00Z"
            assert field.original_units == "K"
            for lat_index, lon_index in ((0, 0), (200, 500), (360, 1000), (720, 1439)):
                latitude = float(ds.latitude[lat_index])
                longitude = float(ds.longitude[lon_index])
                i = np.flatnonzero(field.latitude == latitude)[0]
                j = np.flatnonzero(field.longitude == longitude)[0]
                expected = float(ds.t2m[index, lat_index, lon_index]) - 273.15
                assert field.celsius[i, j] == pytest.approx(expected)
