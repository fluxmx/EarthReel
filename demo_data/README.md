# ERA5 2 m temperature demo

This directory contains an unmodified ERA5 subset for reproducible EarthReel examples.

| Property | Value |
| --- | --- |
| File | `demo-t2m-2000_01_01_00-01-02.nc` |
| Variable | `t2m(valid_time, latitude, longitude)` — 2 metre temperature |
| Units | K (EarthReel converts to °C for display) |
| Times | 2000-01-01 00:00, 01:00, 02:00 UTC |
| Grid | Global, regular 0.25°, 721 latitudes × 1440 longitudes |
| Latitude | 90° to −90°, descending |
| Longitude | 0° to 359.75° |
| Size | 4,514,590 bytes |
| SHA-256 | `1446569402ff1142f2a96988d2eeb6ca4ca9cb7c98d2d288878152cd2f3d6e2a` |

## Source and attribution

ERA5 hourly data on single levels from 1940 to present, produced by ECMWF for the Copernicus Climate Change Service (C3S), retrieved via the Copernicus Climate Data Store (CDS).

- [Dataset and documentation](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=documentation)
- Dataset DOI: [10.24381/cds.adbb2d47](https://doi.org/10.24381/cds.adbb2d47)
- [ECMWF attribution guidance](https://confluence.ecmwf.int/pages/viewpage.action?navigatingVersions=true&pageId=673339011)

© European Centre for Medium-Range Weather Forecasts (ECMWF), 2026, retrieved via the Copernicus Climate Data Store. Contains Copernicus Climate Change Service information (2026). Neither the European Commission nor ECMWF is responsible for any use that may be made of this information.

## Data licence

The ERA5 data file is distributed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/), separately from EarthReel's Apache-2.0 code licence. Retain attribution when sharing the data or derived products, and indicate modifications. The NetCDF file is preserved as supplied; its history records conversion from GRIB to NetCDF on 2026-11-02. Display conversion to °C and any colour clipping are documented in generated outputs.

To retrieve an equivalent subset, select reanalysis, 2 metre temperature, 2000-01-01, 00:00/01:00/02:00 UTC, global coverage, regular 0.25° grid, and NetCDF output in CDS. A fresh download may have different metadata and compression, so its bytes need not match the bundled file.
