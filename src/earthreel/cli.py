# Copyright 2026 fluxmx
# SPDX-License-Identifier: Apache-2.0

"""Command-line entry point for EarthReel."""

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from earthreel import __version__


def main() -> None:
    """Render a still or a fixed-time rotating globe from a YAML scene."""
    parser = argparse.ArgumentParser(
        prog="earthreel",
        description="Render Earth science data as globe images and movies.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    for command, help_text in (("snapshot", "Export a PNG"), ("render", "Export an MP4 orbit")):
        sub = commands.add_parser(command, help=help_text)
        sub.add_argument("scene", type=Path, help="YAML scene configuration")
        sub.add_argument("--output", type=Path, required=True)
        sub.add_argument("--time-index", type=int, help="Override the selected time index")
        sub.add_argument(
            "--layout", choices=("single", "dual"), help="Choose one or two globe views"
        )
        sub.add_argument("--width", type=int, help="Override output width")
        sub.add_argument("--height", type=int, help="Override output height")
        sub.add_argument("--fps", type=int, help="Override movie frame rate")
        sub.add_argument("--duration", type=float, help="Override movie duration in seconds")
        sub.add_argument("--crf", type=int, help="H.264 quality: 0..51, lower is higher quality")
        sub.add_argument("--preset", help="H.264 encoding speed preset, default slow")
        sub.add_argument("--overwrite", action="store_true", help="Replace output and run record")
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    try:
        # Keep help/version usable without initializing the scientific/rendering stack.
        import yaml

        from earthreel.config import load_config
        from earthreel.render import export_scene

        config = load_config(args.scene)
        if args.layout is not None:
            config = replace(config, display=replace(config.display, layout=args.layout))
        if args.time_index is not None:
            config = replace(config, data=replace(config.data, time_index=args.time_index))
        overrides = {
            name: getattr(args, name)
            for name in ("width", "height", "fps", "duration", "crf", "preset")
            if getattr(args, name) is not None
        }
        config = replace(config, output=replace(config.output, **overrides))

        def progress(done, total):
            if done == 1 or done == total or done % config.output.fps == 0:
                print(f"Rendering {done}/{total} frames", file=sys.stderr, flush=True)

        result = export_scene(
            config,
            args.output,
            movie=args.command == "render",
            overwrite=args.overwrite,
            progress=progress,
        )
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as error:
        parser.exit(2, f"earthreel: {error}\n")
    print(f"Saved {result.output}\nRun record: {result.metadata}")
