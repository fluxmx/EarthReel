# Copyright 2026 fluxmx
# SPDX-License-Identifier: Apache-2.0
"""Shared globe scene and streaming PNG/MP4 export."""

import hashlib
import json
import platform
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

import numpy as np
import pyvista as pv

from earthreel import __version__
from earthreel.config import SceneConfig
from earthreel.data import ScalarField, TemperatureField, load_field


def temperature_lut(config: SceneConfig) -> pv.LookupTable:
    """Map numerical temperatures through a shared, optionally centred colour table."""
    from matplotlib import colormaps
    from matplotlib.colors import Normalize, TwoSlopeNorm

    display = config.display
    normalizer = (
        Normalize(vmin=display.vmin, vmax=display.vmax)
        if display.vcenter is None
        else TwoSlopeNorm(vmin=display.vmin, vcenter=display.vcenter, vmax=display.vmax)
    )
    values = np.linspace(display.vmin, display.vmax, 1025)
    colors = colormaps[display.cmap](normalizer(values))
    table = pv.LookupTable()
    table.values = np.rint(colors * 255).astype(np.uint8)
    table.scalar_range = (display.vmin, display.vmax)
    table.nan_color = "#616b76"
    return table


def asset_path(name: str) -> Path:
    return Path(str(files("earthreel").joinpath("assets", name)))


def base_globe() -> pv.StructuredGrid:
    """Opaque, georeferenced base surface with a duplicated UV seam at 180°."""
    longitude, latitude = np.meshgrid(
        np.linspace(-180, 180, 361), np.linspace(-90, 90, 181), indexing="ij"
    )
    lon, lat = np.deg2rad(longitude), np.deg2rad(latitude)
    radius = 0.998
    mesh = pv.StructuredGrid(
        radius * np.cos(lat) * np.cos(lon),
        radius * np.cos(lat) * np.sin(lon),
        radius * np.sin(lat),
    )
    mesh.active_texture_coordinates = np.column_stack(
        (
            ((longitude + 180) / 360).ravel(order="F"),
            ((latitude + 90) / 180).ravel(order="F"),
        )
    )
    return mesh


def _sphere_geometry(lat: np.ndarray, lon: np.ndarray) -> pv.PolyData:
    """Connect longitude cyclically and close both poles without degenerate faces."""
    interior = ~np.isclose(np.abs(lat), 90, atol=1e-7)
    rings = lat[interior]
    if not rings.size:
        raise ValueError("Grid has no latitude rows between the poles")
    phi, theta = np.meshgrid(np.deg2rad(rings), np.deg2rad(lon), indexing="ij")
    points = np.column_stack(
        (
            (np.cos(phi) * np.cos(theta)).ravel(),
            (np.cos(phi) * np.sin(theta)).ravel(),
            np.sin(phi).ravel(),
        )
    )
    south, north = len(points), len(points) + 1
    points = np.vstack((points, [0, 0, -1], [0, 0, 1]))
    nlon = lon.size
    cols = np.arange(nlon)
    following = (cols + 1) % nlon
    rows = np.arange(rings.size - 1)[:, None] * nlon
    a = (rows + cols).ravel()
    b = (rows + following).ravel()
    quads = np.column_stack((np.full(a.size, 4), a, b, b + nlon, a + nlon))
    south_cap = np.column_stack((np.full(nlon, 3), np.full(nlon, south), following, cols))
    last = (rings.size - 1) * nlon
    north_cap = np.column_stack(
        (
            np.full(nlon, 3),
            np.full(nlon, north),
            last + cols,
            last + following,
        )
    )
    mesh = pv.PolyData(
        points, np.concatenate((quads.ravel(), south_cap.ravel(), north_cap.ravel()))
    )
    return mesh


def globe_mesh(field: ScalarField | TemperatureField) -> pv.PolyData:
    """Point scalars for optional continuous interpolation; polar rows are averaged."""
    mesh = _sphere_geometry(field.latitude, field.longitude)
    interior = ~np.isclose(np.abs(field.latitude), 90, atol=1e-7)
    values = field.values
    mesh["scalar_value"] = np.r_[
        values[interior].ravel(),
        float(np.mean(values[0])),
        float(np.mean(values[-1])),
    ]
    return mesh


def cell_globe_mesh(field: ScalarField | TemperatureField) -> pv.PolyData:
    """Give each original sample its own constant-colour cell, with no averaging."""
    lat, lon = field.latitude, field.longitude
    latitude_edges = np.r_[-90, (lat[:-1] + lat[1:]) / 2, 90]
    longitude_edges = lon - (lon[1] - lon[0]) / 2
    mesh = _sphere_geometry(latitude_edges, longitude_edges)
    # Geometry emits interior quads, then south and north polar triangles.
    mesh.cell_data["scalar_value"] = np.r_[
        field.values[1:-1].ravel(),
        field.values[0],
        field.values[-1],
    ]
    return mesh


def camera_position(longitude: float, latitude: float) -> tuple:
    lon, lat = np.deg2rad([longitude, latitude])
    eye = 4 * np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    return tuple(eye), (0, 0, 0), (0, 0, 1)


def set_camera_views(plotter: pv.Plotter, longitude: float, latitude: float) -> None:
    """Update one view or keep the two viewing directions antipodal."""
    views = ((longitude, latitude), (longitude + 180, -latitude))
    for column, (lon, lat) in enumerate(views[: plotter.shape[1]]):
        plotter.subplot(0, column)
        plotter.camera_position = camera_position(lon, lat)
    plotter.subplot(0, 0)


def make_plotter(config: SceneConfig, field: ScalarField | TemperatureField) -> pv.Plotter:
    """Create the selected globe layout and shared screen-space annotations."""
    width, height = config.output.width, config.output.height
    dual = config.display.layout == "dual"
    columns = 2 if dual else 1
    plotter = pv.Plotter(
        off_screen=True, window_size=(width, height), shape=(1, columns), border=False
    )
    try:
        # Share data, geometry and colour mapping; only the cameras differ.
        nearest = config.display.interpolation == "nearest"
        surface = cell_globe_mesh(field) if nearest else globe_mesh(field)
        base = base_globe()
        # Keep the base below even coarse polygon facets (also useful for synthetic tests).
        lat_step = float(np.max(np.diff(field.latitude)))
        lon_step = float(np.max(np.diff(np.r_[field.longitude, field.longitude[0] + 360])))
        base.points *= np.cos(np.deg2rad(lat_step / 2)) * np.cos(np.deg2rad(lon_step / 2))
        texture = pv.read_texture(asset_path("land_ocean_ice_2048.png"))
        table = temperature_lut(config)
        for column in range(columns):
            plotter.subplot(0, column)
            if dual:
                plotter.renderer.SetViewport((0, 0, 0.46, 1) if column == 0 else (0.46, 0, 1, 1))
            plotter.set_background("#000000", all_renderers=False)
            plotter.add_mesh(
                base,
                texture=texture,
                opacity=1.0,
                lighting=False,
                show_scalar_bar=False,
                name="earth_base",
            )
            plotter.add_mesh(
                surface,
                scalars="scalar_value",
                cmap=table,
                clim=(config.display.vmin, config.display.vmax),
                lighting=False,
                show_scalar_bar=False,
                nan_color="#616b76",
                nan_opacity=1,
                preference="cell" if nearest else "point",
                interpolate_before_map=not nearest,
                opacity=1.0,
                culling="back",
                name="field",
            )
            plotter.enable_parallel_projection()
            plotter.camera.parallel_scale = 1.30 if dual else 1.18
            plotter.camera.SetWindowCenter(
                (-0.05 if column == 0 else 0.19) if dual else 0.10,
                0.04,
            )
        set_camera_views(plotter, config.camera.longitude, config.camera.latitude)

        # A transparent overlay renderer spans the whole output, independent of camera motion.
        from vtkmodules.vtkRenderingCore import vtkRenderer

        overlay = vtkRenderer()
        plotter.render_window.SetNumberOfLayers(2)
        overlay.SetLayer(1)
        overlay.SetInteractive(False)
        overlay.SetViewport(0, 0, 1, 1)
        plotter.render_window.AddRenderer(overlay)

        from vtkmodules.vtkCommonCore import VTK_FONT_FILE
        from vtkmodules.vtkRenderingCore import (
            vtkActor2D,
            vtkCoordinate,
            vtkPolyDataMapper2D,
            vtkTextActor,
        )

        scale = height / 1080
        header_font_size = 34  # Shared by single/dual layouts at the same output resolution.

        def text(
            content,
            x,
            y,
            size,
            color="#e6edf3",
            centered=False,
            right_aligned=False,
            horizontally_centered=False,
            max_width=None,
        ):
            actor = vtkTextActor()
            actor.SetInput(content)
            actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedViewport()
            actor.SetPosition(x, y)
            prop = actor.GetTextProperty()
            prop.SetFontFamily(VTK_FONT_FILE)
            prop.SetFontFile(str(asset_path("fonts/NotoSans-Regular.ttf")))
            font_size = max(7, round(size * scale))
            if max_width is not None:
                from PIL import ImageFont

                font = ImageFont.truetype(str(asset_path("fonts/NotoSans-Regular.ttf")), font_size)
                measured = font.getlength(content)
                if measured > max_width * width:
                    font_size = max(7, int(font_size * max_width * width / measured))
            prop.SetFontSize(font_size)
            prop.SetColor(pv.Color(color).float_rgb)
            if centered:
                prop.SetVerticalJustificationToCentered()
            if right_aligned:
                prop.SetJustificationToRight()
            elif horizontally_centered:
                prop.SetJustificationToCentered()
            overlay.AddViewProp(actor)

        from vtkmodules.vtkRenderingCore import vtkTexturedActor2D

        logo_texture = pv.read_texture(asset_path("earthreel-logo-dark.png"))
        logo_texture.InterpolateOn()
        logo_height = 0.048
        logo_width = (
            logo_height * height / width * logo_texture.dimensions[0] / logo_texture.dimensions[1]
        )
        logo_geometry = pv.PolyData(
            np.array(
                [
                    [0.035, 0.931, 0],
                    [0.035 + logo_width, 0.931, 0],
                    [0.035 + logo_width, 0.931 + logo_height, 0],
                    [0.035, 0.931 + logo_height, 0],
                ]
            ),
            np.array([4, 0, 1, 2, 3]),
        )
        logo_geometry.active_texture_coordinates = np.array(
            [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        )
        logo_mapper = vtkPolyDataMapper2D()
        logo_mapper.SetInputData(logo_geometry)
        logo_coordinate = vtkCoordinate()
        logo_coordinate.SetCoordinateSystemToNormalizedViewport()
        logo_mapper.SetTransformCoordinate(logo_coordinate)
        logo_actor = vtkTexturedActor2D()
        logo_actor.SetMapper(logo_mapper)
        logo_actor.SetTexture(logo_texture)
        # Isolate textured overlay state from text and colour-bar geometry.
        logo_overlay = vtkRenderer()
        plotter.render_window.SetNumberOfLayers(3)
        logo_overlay.SetLayer(2)
        logo_overlay.SetInteractive(False)
        logo_overlay.SetViewport(0, 0, 1, 1)
        logo_overlay.AddViewProp(logo_actor)
        plotter.render_window.AddRenderer(logo_overlay)
        title_x = 0.035 + logo_width + 0.035
        text("|", title_x - 0.02, 0.955, 30, "#617889", centered=True)
        text(
            config.display.title or field.long_name,
            title_x,
            0.955,
            header_font_size,
            centered=True,
            max_width=0.64 - title_x,
        )
        text(
            field.time_utc.replace("T", " ").replace("Z", " UTC"),
            0.88,
            0.955,
            header_font_size,
            centered=True,
            right_aligned=True,
        )
        text(field.display_units, 0.925, 0.88, 24)
        # text("Grey: missing", (0.925 + 0.945) / 2, 0.10, 14, "#b9c9d7", horizontally_centered=True)

        # Use the scientific layer's exact LUT for a tall bar with triangular extensions.
        # Native VTK scalar-bar range swatches are square, so build these screen-space cells.
        lut = plotter.actors["field"].mapper.lookup_table
        left, right, bottom, top, extension = 0.925, 0.945, 0.19, 0.82, 0.025
        points, faces, colors = [], [], []

        def polygon(vertices, color):
            start = len(points)
            points.extend((x, y, 0) for x, y in vertices)
            faces.extend([len(vertices), *range(start, start + len(vertices))])
            colors.append(np.rint(np.asarray(color) * 255).astype(np.uint8))

        count = lut.GetNumberOfTableValues()
        for index in range(count):
            low = bottom + (top - bottom) * index / count
            high = bottom + (top - bottom) * (index + 1) / count
            polygon(
                [(left, low), (right, low), (right, high), (left, high)], lut.GetTableValue(index)
            )
        middle = (left + right) / 2
        polygon(
            [(left, bottom), (middle, bottom - extension), (right, bottom)], lut.GetTableValue(0)
        )
        polygon(
            [(left, top), (right, top), (middle, top + extension)], lut.GetTableValue(count - 1)
        )
        geometry = pv.PolyData(np.asarray(points), np.asarray(faces))
        geometry.cell_data["rgba"] = np.asarray(colors)
        mapper = vtkPolyDataMapper2D()
        mapper.SetInputData(geometry)
        mapper.SetScalarModeToUseCellData()
        mapper.SetColorModeToDirectScalars()
        coordinate = vtkCoordinate()
        coordinate.SetCoordinateSystemToNormalizedViewport()
        mapper.SetTransformCoordinate(coordinate)
        bar = vtkActor2D()
        bar.SetMapper(mapper)
        overlay.AddViewProp(bar)
        for index, value in enumerate(np.linspace(config.display.vmin, config.display.vmax, 6)):
            value = 0 if abs(value) < 1e-10 else value
            text(f"{value:g}", 0.955, bottom + (top - bottom) * index / 5, 21, centered=True)
        return plotter
    except Exception:
        plotter.close()
        raise


@dataclass(frozen=True)
class ExportResult:
    output: Path
    metadata: Path
    frames: int


def export_scene(
    config: SceneConfig,
    output: Path,
    *,
    movie: bool = False,
    overwrite: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> ExportResult:
    """Export into temporary files, then publish the completed media and run record."""
    config.validate()
    output = output.resolve()
    expected = ".mp4" if movie else ".png"
    if output.suffix.lower() != expected:
        raise ValueError(f"Output must have the {expected} extension")
    metadata = output.with_suffix(output.suffix + ".json")
    if not overwrite and (output.exists() or metadata.exists()):
        raise FileExistsError(f"Output or run record already exists: {output}; use --overwrite")
    field = load_field(config.data)
    with config.data.path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = config.output.frames if movie else 1
    with tempfile.TemporaryDirectory(prefix=".earthreel-", dir=output.parent) as temporary:
        temp_output = Path(temporary) / output.name
        plotter = make_plotter(config, field)
        try:
            if movie:
                plotter.open_movie(
                    str(temp_output),
                    framerate=config.output.fps,
                    codec="libx264",
                    quality=None,
                    pixelformat="yuv420p",
                    macro_block_size=1,
                    output_params=[
                        "-crf",
                        str(config.output.crf),
                        "-preset",
                        config.output.preset,
                        "-g",
                        str(config.output.fps * 5),
                        "-bf",
                        "3",
                        "-movflags",
                        "+faststart",
                    ],
                )
                plotter.show(auto_close=False, interactive=False)
                for index in range(frames):
                    angle = config.camera.longitude + 360 * index / frames
                    set_camera_views(plotter, angle, config.camera.latitude)
                    plotter.write_frame()
                    if progress:
                        progress(index + 1, frames)
            else:
                # Capture after initialization so overlay textures/text are ready on macOS.
                plotter.show(auto_close=False, interactive=False)
                plotter.screenshot(str(temp_output))
        finally:
            plotter.close()
        if not temp_output.exists() or temp_output.stat().st_size == 0:
            raise RuntimeError("Renderer did not produce a non-empty output")
        record = {
            "created_at_utc": datetime.now(UTC).isoformat(),
            "config": config.to_dict(),
            "data_sha256": digest,
            "selected_time_utc": field.time_utc,
            "original_units": field.original_units,
            "display_units": "degrees Celsius" if field.display_units == "°C" else field.display_units,
            "colour_mapping": {
                "cmap": config.display.cmap,
                "vmin": config.display.vmin,
                "vcenter": config.display.vcenter,
                "vmax": config.display.vmax,
                "normalization": "linear" if config.display.vcenter is None else "two-slope",
            },
            "variable_long_name": field.long_name,
            "spatial_interpolation": config.display.interpolation,
            "views": [
                {"longitude": config.camera.longitude, "latitude": config.camera.latitude},
                {
                    "longitude": (config.camera.longitude + 180) % 360,
                    "latitude": -config.camera.latitude,
                },
            ][: 2 if config.display.layout == "dual" else 1],
            "layout": config.display.layout,
            "logo": "EarthReel vector wordmark; video uses the bundled PNG derived from the SVG artwork",
            "grid_shape": list(field.values.shape),
            "valid_range": [float(np.nanmin(field.values)), float(np.nanmax(field.values))],
            **({"valid_range_c": [float(np.nanmin(field.values)), float(np.nanmax(field.values))]}
               if field.display_units == "°C" else {}),
            "missing_values": int(np.isnan(field.values).sum()),
            "base_map": "NASA Blue Marble, bundled opaque RGB texture on radius 0.998 sphere",
            "font": "Noto Sans Regular, SIL Open Font License 1.1",
            "processing": [
                (
                    "Kelvin to Celsius when needed; no spatial downsampling"
                    if field.display_units == "°C"
                    else "Velocity retained in m/s; no spatial downsampling"
                ),
                "Sorted latitude and cyclic longitude with values; poles collapsed to single vertices",
                (
                    "One constant-colour cell per source sample; midpoint cell boundaries; no averaging"
                    if config.display.interpolation == "nearest"
                    else "Polar vertex uses mean of source polar row; point scalars interpolated"
                ),
                "Display colours clipped to configured vmin/vmax; numerical data unchanged",
                "Opaque Earth base; opaque scientific layer with back-face culling",
                "Fixed data time; uniform orbit in the selected layout; no duplicated endpoint frame",
            ],
            "output": str(output),
            "frame_count": frames,
            "encoding": {
                "codec": "libx264",
                "pixel_format": "yuv420p",
                "crf": config.output.crf,
                "preset": config.output.preset,
                "gop_max_frames": config.output.fps * 5,
                "b_frames": 3,
                "faststart": True,
            }
            if movie
            else None,
            "versions": {
                "earthreel": __version__,
                "python": platform.python_version(),
                **{
                    package: version(package)
                    for package in (
                        "numpy",
                        "xarray",
                        "netCDF4",
                        "pyvista",
                        "vtk",
                        "PyYAML",
                        "imageio-ffmpeg",
                    )
                },
            },
        }
        temp_record = Path(temporary) / metadata.name
        temp_record.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        # Recheck after a long render before replacing existing products.
        if not overwrite and (output.exists() or metadata.exists()):
            raise FileExistsError(f"Output appeared while rendering: {output}; use --overwrite")
        temp_output.replace(output)
        temp_record.replace(metadata)
    return ExportResult(output, metadata, frames)
