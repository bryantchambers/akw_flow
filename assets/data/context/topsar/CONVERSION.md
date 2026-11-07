# TOPSAR preview conversion — 6 November 2026

The original acquisition and inspection files remain as historical records. The raw `ts1260_c.demi2` is unchanged. A reproducible preview conversion is now implemented in `scripts/build_topsar_scenes.py`.

## What is resolved

The raw DEM is a big-endian signed 16-bit AIRSAR product with a documented header offset, elevation increment and offset. Its horizontal coordinates are **SCH (spherical cross-track height)**, not a ready-made UTM raster. The source's UTM label is explicitly described as not implemented by the AIRSAR format documentation.

The converter uses PROJ's SCH operation, the source peg latitude/longitude, heading, S0/C0 and 5 m posts. It reproduces all four DEM-header corner coordinates with a maximum residual of approximately **0.67 m**. This is an internal metadata consistency check, not an independent positional accuracy measurement. Pixel-centre coordinates are preserved separately from the outer fence extent.

Source sphere-relative heights are converted through SCH to **WGS84 ellipsoidal metres**. No geoid correction, empirical height offset, registration shift or Copernicus infill is applied. These heights must not be directly mixed with Copernicus EGM2008 orthometric heights.

## What remains provisional

Repeated raw DN `-16384` is provisionally excluded from display as a suspected fill/saturation value. This is an explicit preview policy, not a fully verified product-wide NoData definition. Raw values remain intact. Other radar outliers and surface effects remain. Gaps are actual missing triangles in the viewer; they are not filled with a fabricated surface.

The 5 m post spacing does not establish 5 m effective resolution or positional/vertical accuracy. The processing log reports about 10.8 m nominal azimuth resolution. Independent ground-control checks, vertical validation, full quality-flag interpretation and assessment of vegetation/radar artefacts remain necessary before hydraulic use.

## Selectable products

- **TOPSAR / Angkor Wat / 5 m detail:** approximately 2 × 2 km; 400 × 400 displayed posts, approximately 5 m spacing. About 94.7% of display cells survive the provisional mask.
- **TOPSAR / survey strip / 80 m overview:** full bounding extent of the narrow strip, sampled at approximately 80 m for a practical browser overview. Outside-strip cells and suspected fill remain holes.
- Copernicus remains a separate selectable context layer. No TOPSAR drainage accumulation, discharge or bacterial hotspot output is inferred.

`conversion_provenance.json` records exact extents, transforms, hashes, sample counts, mask policy and numerical checks. Generated TIFFs are local/reproducible; the compact viewer scenes and raw source are retained with the project.

## Reproduce and verify

```bash
.venv/bin/pip install -r scripts/requirements-gis.txt
.venv/bin/python scripts/build_topsar_scenes.py
.venv/bin/python -m unittest discover -s tests -v
```

Tests check raw identity/header layout, corner agreement, an independent SCH-to-ECEF calculation, native detail spacing, preservation of gaps and absence of invented flow results. Browser checks additionally exercise source switching, legends, overlay controls, imports and mobile rendering.

Primary references: [AIRSAR format](https://airsar.jpl.nasa.gov/data/data_format.pdf), [reading TOPSAR heights](https://airsar.jpl.nasa.gov/data/getting_started.html), [JPL geocoding method](https://ntrs.nasa.gov/api/citations/19980045325/downloads/19980045325.pdf), [PROJ SCH](https://proj.org/en/stable/operations/projections/sch.html).
