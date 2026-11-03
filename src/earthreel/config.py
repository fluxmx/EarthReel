# Copyright 2026 fluxmx
# SPDX-License-Identifier: Apache-2.0
"""Validated scene configuration shared by image and movie export."""

import math
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DataConfig:
    path: Path
    variable: str = "t2m"
    latitude: str = "latitude"
    longitude: str = "longitude"
    time: str = "valid_time"
    time_index: int = 0


@dataclass(frozen=True)
class DisplayConfig:
    layout: str = "dual"
    interpolation: str = "nearest"
    title: str = ""
    source: str = ""
    attribution: str = ""
    cmap: str = "coolwarm"
    vmin: float = -60
    vmax: float = 40
    vcenter: float | None = 0


@dataclass(frozen=True)
class OutputConfig:
    width: int = 2560
    height: int = 1440
    fps: int = 60
    duration: float = 20
    crf: int = 22
    preset: str = "slow"

    @property
    def frames(self) -> int:
        return round(self.fps * self.duration)


@dataclass(frozen=True)
class CameraConfig:
    longitude: float = 110
    latitude: float = 30


@dataclass(frozen=True)
class SceneConfig:
    data: DataConfig
    display: DisplayConfig = field(default_factory=DisplayConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)

    def validate(self) -> None:
        def number(value, name):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")

        if type(self.data.time_index) is not int or self.data.time_index < 0:
            raise ValueError("data.time_index must be a non-negative integer")
        for name in ("variable", "latitude", "longitude", "time"):
            if not isinstance(getattr(self.data, name), str) or not getattr(self.data, name):
                raise ValueError(f"data.{name} must be a non-empty string")
        for f in fields(self.display):
            value = getattr(self.display, f.name)
            if f.name == "vcenter" and value is None:
                continue
            if f.name in ("vmin", "vmax", "vcenter"):
                number(value, f"display.{f.name}")
            elif not isinstance(value, str):
                raise ValueError(f"display.{f.name} must be a string")
        if self.display.vmin >= self.display.vmax:
            raise ValueError("display.vmin must be less than display.vmax")
        if self.display.layout not in ("single", "dual"):
            raise ValueError("display.layout must be 'single' or 'dual'")
        if self.display.interpolation not in ("nearest", "linear"):
            raise ValueError("display.interpolation must be 'nearest' or 'linear'")
        if self.display.vcenter is not None and not (
            self.display.vmin < self.display.vcenter < self.display.vmax
        ):
            raise ValueError("display.vcenter must be strictly between vmin and vmax, or null")
        for name in ("width", "height", "fps"):
            value = getattr(self.output, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"output.{name} must be a positive integer")
        if min(self.output.width, self.output.height) < 128:
            raise ValueError("output dimensions must be at least 128 pixels")
        if self.output.width % 2 or self.output.height % 2:
            raise ValueError("output width and height must be even for H.264 yuv420p")
        if type(self.output.crf) is not int or not 0 <= self.output.crf <= 51:
            raise ValueError("output.crf must be an integer between 0 and 51")
        if self.output.preset not in (
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ):
            raise ValueError("output.preset must be a valid x264 speed preset")
        number(self.output.duration, "output.duration")
        if self.output.duration <= 0 or self.output.frames < 1:
            raise ValueError("output.duration must produce at least one frame")
        for name in ("longitude", "latitude"):
            number(getattr(self.camera, name), f"camera.{name}")
        if not -89 <= self.camera.latitude <= 89:
            raise ValueError("camera.latitude must be between -89 and 89 degrees")

    def to_dict(self) -> dict:
        result = asdict(self)
        result["data"]["path"] = str(self.data.path)
        return result


def load_config(path: Path) -> SceneConfig:
    path = path.resolve()
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict) or not isinstance(raw.get("data"), dict):
        raise ValueError("Scene must be a YAML mapping with a data section")
    sections = {
        "data": DataConfig,
        "display": DisplayConfig,
        "output": OutputConfig,
        "camera": CameraConfig,
    }
    if unknown := raw.keys() - sections.keys():
        raise ValueError(f"Unknown scene sections: {sorted(unknown)}")
    values = {}
    for name, cls in sections.items():
        section = raw.get(name, {})
        if not isinstance(section, dict):
            raise ValueError(f"{name} must be a mapping")
        section = dict(section)
        if unknown := section.keys() - {f.name for f in fields(cls)}:
            raise ValueError(f"Unknown {name} options: {sorted(unknown)}")
        if name == "data":
            if not isinstance(section.get("path"), str) or not section["path"]:
                raise ValueError("data.path must be a non-empty file path")
            section["path"] = (path.parent / section["path"]).resolve()
        values[name] = cls(**section)
    config = SceneConfig(**values)
    config.validate()
    return config
