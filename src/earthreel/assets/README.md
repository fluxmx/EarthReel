# Bundled visual assets

## EarthReel wordmark

`earthreel-logo.svg` and `earthreel-logo-dark.svg` are original EarthReel vector artwork, licensed under Apache-2.0. The wordmark combines an orbital globe, bold outlined "Earth", forward-slanted teal "Reel", three solid film-frame accents and a thick motion ribbon. The text remains the main element. Stroke widths are at least 6.5 SVG points, with an 8-point ribbon, to stay legible in the video header. All letters are vector paths: no embedded bitmap or runtime font dependency.

README uses the light/dark SVG variants. Video uses `earthreel-logo-dark.png`, rendered from the same outline geometry with transparency. Rebuild all variants with `python scripts/build_logo.py` in the development environment. The SVG is the scalable deliverable; the PNG is only a rendering derivative for VTK.

The third-party assets below are not relicensed under EarthReel's Apache-2.0 licence.

## NASA Blue Marble

- File: `land_ocean_ice_2048.png`, unmodified 2048 × 1024 RGB image.
- Source: https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57730/land_ocean_ice_2048.png
- Description: https://science.nasa.gov/resource/blue-marble/
- Credit: NASA / Blue Marble, land surface, ocean colour and sea ice.
- Usage: NASA imagery reuse under https://www.nasa.gov/nasa-brand-center/images-and-media/ and https://science.nasa.gov/earth/faq/ . No NASA endorsement is implied.
- SHA-256: `b5e0139834c638d10c2c747f4bac63df5f9387680c00d87e5a2a9ed9a3dfea71`.

The texture is placed beneath the scientific layer as a fully opaque Earth base. It is not a contemporaneous observation of the selected ERA5 time. Valid temperature values remain opaque and retain their original colour mapping.

## Noto Sans Regular

- Files: `fonts/NotoSans-Regular.ttf` and `fonts/NotoSans-Bold.ttf`, unmodified static fonts. Regular is used for screen labels; Bold is used for both words in the logo.
- Source: https://github.com/notofonts/noto-fonts/blob/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf
- Bold source: https://github.com/notofonts/noto-fonts/blob/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf
- Copyright and licence: see `fonts/OFL.txt` (SIL Open Font License 1.1).
- The licence permits commercial use and redistribution subject to its terms.

All current English labels and colour-bar values use this exact font file instead of operating-system font substitution. This Latin/Greek/Cyrillic font is not a CJK font; Chinese labels would require the corresponding Noto Sans CJK font.
