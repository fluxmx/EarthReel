import json
import os
from dataclasses import replace

import imageio.v2 as iio
import numpy as np
import pytest
from PIL import Image

from earthreel.config import CameraConfig, DisplayConfig, OutputConfig, SceneConfig
from earthreel.data import TemperatureField
from earthreel.render import asset_path, export_scene, make_plotter, set_camera_views

pytestmark = [
    pytest.mark.render,
    pytest.mark.skipif(
        os.environ.get("EARTHREEL_RENDER_TESTS") != "1",
        reason="Set EARTHREEL_RENDER_TESTS=1 with a working OpenGL context",
    ),
]


@pytest.mark.parametrize("layout", ["single", "dual"])
def test_image_movie_metadata_and_overwrite(dataset, tmp_path, layout):
    config = SceneConfig(
        data=dataset(),
        output=OutputConfig(width=480, height=270, fps=3, duration=2),
        display=DisplayConfig(layout=layout),
    )
    image = export_scene(config, tmp_path / "still.png")
    with Image.open(image.output) as png:
        assert png.size == (480, 270)
        pixels = np.asarray(png)
        assert pixels[7:19, 20:75].std() > 10  # The logo must actually be visible.
        assert pixels[7:20, 80:270].std() > 10  # Title shares the logo's header row.
        assert pixels[7:20, 320:425].std() > 10  # UTC time is on that same row.
        assert pixels[50:210, 440:455].std() > 20  # Shared colour bar is still rendered.
        # The globe itself must be present, not just the colour bar / annotations.
        if layout == "dual":
            assert pixels[60:210, 35:200].std() > 20
            assert pixels[60:210, 240:400].std() > 20
        else:
            assert pixels[60:210, 90:300].std() > 20
    metadata = json.loads(image.metadata.read_text())
    assert metadata["selected_time_utc"] == "2000-01-01T00:00:00Z"
    assert metadata["frame_count"] == 1
    assert metadata["layout"] == layout
    assert len(metadata["views"]) == (2 if layout == "dual" else 1)
    assert len(metadata["data_sha256"]) == 64
    with pytest.raises(FileExistsError):
        export_scene(config, image.output)
    export_scene(config, image.output, overwrite=True)
    movie = export_scene(config, tmp_path / "orbit.mp4", movie=True)
    with iio.get_reader(str(movie.output), format="ffmpeg") as reader:
        info = reader.get_meta_data()
        assert info["size"] == (480, 270)
        assert info["fps"] == 3
        assert info["pix_fmt"] == "yuv420p(progressive)" or info["pix_fmt"] == "yuv420p"
        assert reader.count_frames() == 6
        frames = [reader.get_data(i) for i in range(6)]
        assert np.mean(np.abs(frames[0].astype(float) - frames[2])) > 1
        # A camera orbit must not move the header / colour bar.
        header_a = frames[0][:22].astype(float).ravel()
        header_b = frames[2][:22].astype(float).ravel()
        assert np.corrcoef(header_a, header_b)[0, 1] > 0.98
    record = json.loads(movie.metadata.read_text())
    assert record["frame_count"] == 6
    assert record["encoding"]["crf"] == 22
    assert record["encoding"]["preset"] == "slow"
    assert record["config"]["data"]["time_index"] == 0
    # The time index is also reflected in the actual selected data, not only metadata.
    with pytest.raises(ValueError, match="out of range"):
        export_scene(replace(config, data=replace(config.data, time_index=2)), tmp_path / "bad.png")


def test_failed_export_cleans_temporary_files(dataset, tmp_path, monkeypatch):
    config = SceneConfig(data=dataset(), output=OutputConfig(width=320, height=180))

    def fail(*args, **kwargs):
        raise RuntimeError("simulated renderer failure")

    monkeypatch.setattr("earthreel.render.make_plotter", fail)
    with pytest.raises(RuntimeError, match="simulated"):
        export_scene(config, tmp_path / "failed.png")
    assert not list(tmp_path.glob(".earthreel-*"))
    assert not (tmp_path / "failed.png").exists()
    assert not (tmp_path / "failed.png.json").exists()


def test_back_hemisphere_cannot_show_through(dataset):
    lat = np.linspace(-90, 90, 19)
    lon = np.arange(0, 360, 10)
    front = np.cos(np.deg2rad(lon)) >= -1e-9
    config = SceneConfig(
        data=dataset(),
        output=OutputConfig(width=480, height=270),
        camera=CameraConfig(longitude=0, latitude=0),
    )
    images = []
    for back_value in (-55, 35):
        values = np.broadcast_to(np.where(front, -10, back_value), (19, 36)).copy()
        plotter = make_plotter(
            config, TemperatureField(lat, lon, values, "2000-01-01T00:00:00Z", "K")
        )
        try:
            actor = plotter.actors["field"]
            assert actor.GetProperty().GetOpacity() == 1
            assert actor.GetProperty().GetBackfaceCulling()
            assert plotter.actors["earth_base"].GetProperty().GetOpacity() == 1
            plotter.show(auto_close=False, interactive=False)
            images.append(plotter.screenshot())
        finally:
            plotter.close()
    # Change only the far hemisphere: the central visible hemisphere stays identical.
    np.testing.assert_array_equal(images[0][90:170, 75:150], images[1][90:170, 75:150])
    assert asset_path("fonts/NotoSans-Regular.ttf").is_file()
    assert asset_path("fonts/OFL.txt").is_file()


def test_two_views_remain_antipodal_during_orbit(dataset):
    config = SceneConfig(data=dataset(), output=OutputConfig(width=640, height=360))
    lat = np.linspace(-90, 90, 19)
    lon = np.arange(0, 360, 10)
    field = TemperatureField(lat, lon, np.zeros((19, 36)), "2000-01-01T00:00:00Z", "K")
    plotter = make_plotter(config, field)
    try:
        for longitude in (0, 110, 230, 359.4):
            set_camera_views(plotter, longitude, 30)
            positions = []
            for column in range(2):
                plotter.subplot(0, column)
                positions.append(np.asarray(plotter.camera.position))
                assert plotter.actors["field"].mapper.lookup_table.scalar_range == (-60, 40)
            np.testing.assert_allclose(positions[0], -positions[1], atol=1e-12)
            assert positions[0][2] > 0 and positions[1][2] < 0
            assert np.rad2deg(
                np.arcsin(positions[0][2] / np.linalg.norm(positions[0]))
            ) == pytest.approx(30)
    finally:
        plotter.close()


def test_velocity_units_and_metadata(dataset, tmp_path):
    config = SceneConfig(
        data=dataset(values=np.linspace(-1, 1, 20).reshape(5, 4), units="m s**-1"),
        display=DisplayConfig(vmin=-1, vmax=1),
        output=OutputConfig(width=480, height=270),
    )
    result = export_scene(config, tmp_path / "velocity.png")
    record = json.loads(result.metadata.read_text())
    assert record["display_units"] == "m/s"
    assert record["valid_range"] == [-1, 1]
    assert "valid_range_c" not in record
    assert "Velocity retained in m/s" in record["processing"][0]
