# Copyright 2026 fluxmx
# SPDX-License-Identifier: Apache-2.0
"""Build outlined SVG wordmarks and matching video PNGs without system fonts.

Run with the project's Python environment: python scripts/build_logo.py
The SVGs contain vector paths, not raster images or external font references.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch, PathPatch
from matplotlib.path import Path as VectorPath
from matplotlib.textpath import TextPath, TextToPath
from matplotlib.transforms import Affine2D

ASSETS = Path(__file__).resolve().parents[1] / "src" / "earthreel" / "assets"


def build():
    bold = FontProperties(fname=str(ASSETS / "fonts/NotoSans-Bold.ttf"), size=110)
    word_start = 105
    advance = TextToPath().get_text_width_height_descent("Earth", bold, False)[0]
    earth = TextPath((word_start, 0), "Earth", size=110, prop=bold)
    reel = TextPath((0, 0), "Reel", size=110, prop=bold).transformed(
        Affine2D().skew_deg(8, 0).translate(word_start + advance + 4, 0)
    )
    right = reel.get_extents().x1
    orbit = VectorPath(
        [(word_start + advance + 16, -14), (right - 65, -42), (right + 12, 5)],
        [VectorPath.MOVETO, VectorPath.CURVE3, VectorPath.CURVE3],
    )
    xmin, xmax, ymin, ymax = -3, right + 24, -34, 94
    aspect = (xmax - xmin) / (ymax - ymin)
    for suffix, earth_color, reel_color in (
        ("", "#173347", "#087f86"),
        ("-dark", "#e6edf3", "#59d8c9"),
    ):
        fig = plt.figure(figsize=(aspect * 1.8, 1.8), dpi=200)
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set(xlim=(xmin, xmax), ylim=(ymin, ymax), aspect="equal")
        ax.axis("off")
        # A bold orbital globe: no hairlines, tiny holes, or external icon/font assets.
        ax.add_patch(Circle((42, 40), 35, fill=False, edgecolor=earth_color, linewidth=7.5))
        ax.add_patch(Ellipse((42, 40), 27, 70, fill=False, edgecolor=reel_color, linewidth=6.5))
        ax.add_patch(Ellipse((42, 40), 70, 25, fill=False, edgecolor=reel_color, linewidth=6.5))
        ax.add_patch(PathPatch(earth, facecolor=earth_color, edgecolor="none"))
        ax.add_patch(PathPatch(reel, facecolor=reel_color, edgecolor="none"))
        # Three solid frames pair with the motion ribbon to suggest film/reel movement.
        for offset in (20, 43, 66):
            ax.add_patch(
                FancyBboxPatch(
                    (word_start + offset, -21),
                    15,
                    9,
                    boxstyle="round,pad=0,rounding_size=2",
                    facecolor=reel_color,
                    edgecolor="none",
                )
            )
        ax.add_patch(
            PathPatch(orbit, facecolor="none", edgecolor=reel_color, linewidth=8, capstyle="round")
        )
        stem = ASSETS / f"earthreel-logo{suffix}"
        with matplotlib.rc_context({"svg.hashsalt": "EarthReel-wordmark-v2"}):
            fig.savefig(
                stem.with_suffix(".svg"),
                transparent=True,
                metadata={
                    "Date": None,
                    "Title": "EarthReel",
                    "Description": "Bold EarthReel wordmark: orbital globe, film frames and motion ribbon.",
                },
            )
        fig.savefig(stem.with_suffix(".png"), transparent=True)
        svg = stem.with_suffix(".svg")
        svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
        plt.close(fig)
        print(stem.with_suffix(".svg"))


if __name__ == "__main__":
    build()
