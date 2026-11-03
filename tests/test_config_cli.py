import subprocess
import sys
from dataclasses import replace

import pytest

from earthreel.config import load_config


def test_relative_data_path_independent_of_cwd(example_path, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    config = load_config(example_path)
    assert config.data.path.is_file()
    assert config.output.frames == 1200


@pytest.mark.parametrize(
    "section,changes",
    [
        ("output", {"width": 321}),
        ("output", {"fps": 0}),
        ("output", {"crf": -1}),
        ("output", {"crf": 52}),
        ("output", {"preset": "unknown"}),
        ("output", {"duration": float("nan")}),
        ("output", {"height": 32}),
        ("display", {"vmin": 50}),
        ("display", {"layout": "triple"}),
        ("data", {"time_index": -1}),
        ("camera", {"latitude": 90}),
    ],
)
def test_invalid_settings(example_path, section, changes):
    config = load_config(example_path)
    config = replace(config, **{section: replace(getattr(config, section), **changes)})
    with pytest.raises(ValueError):
        config.validate()


def test_yaml_error_and_unknown_option(tmp_path):
    path = tmp_path / "bad.yml"
    for content in ("[]", "data: {path: test.nc, typo: 1}", "data: {path: 12}"):
        path.write_text(content)
        with pytest.raises(ValueError):
            load_config(path)


def test_cli_errors_are_concise(example_path, tmp_path):
    for options in (("--time-index", "3"), ("--width", "321")):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "earthreel",
                "snapshot",
                str(example_path),
                "--output",
                str(tmp_path / "bad.png"),
                *options,
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 2
        assert "earthreel:" in result.stderr
        assert "Traceback" not in result.stderr
        assert not (tmp_path / "bad.png").exists()
