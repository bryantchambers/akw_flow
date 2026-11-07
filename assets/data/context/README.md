# Angkor geospatial starter package — 6 November 2026

This is **modern context**, not the reconstructed medieval canal network or high-resolution archaeological terrain. The provisional rectangle is 103.60–104.20° E, 13.20–13.80° N; it is not a delineated watershed or a heritage boundary.

## Acquired

- Two Copernicus GLO-30 Public COG GeoTIFFs from AWS (2021 release), 3600 × 3600 pixels each, approximately 30 m spacing. Horizontal CRS EPSG:4326; height reference EGM2008 metres according to product documentation. This is a DSM including vegetation and structures, not surveyed canal bathymetry. Source: https://registry.opendata.aws/copernicus-dem/ and https://copernicus-dem-30m.s3.amazonaws.com/readme.html . Product reference: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM . Retain its source licence and attribution when distributing derived products.
- Geofabrik Cambodia OSM PBF, snapshot 2026-11-04T21:21:03Z, with provider MD5 checked. Source: https://download.geofabrik.de/asia/cambodia.html . Derived `osm_water_context.geojson` retains 1,524 modern waterway/water-area ways intersecting the search rectangle, source tags and OSM IDs. Complete way geometry is retained; features are not clipped, relation-based multipolygons are not assembled, and historical age/connectivity/dimensions are unverified. © OpenStreetMap contributors, ODbL 1.0: https://www.openstreetmap.org/copyright . The PBF excludes contributor personal information as documented by Geofabrik.
- `provisional_extent.geojson` records the search rectangle. `provenance.json` records sources, retrieval timestamps and hashes; `raster_validation.json` records actual TIFF CRS, dimensions, extents and valid ranges.

Overpass requests failed/time-out; the successful water overlay comes from the dated Geofabrik PBF, not an incomplete Overpass response. Failed endpoint records are retained for provenance.

## 3D viewer and screening

Open `/model-view` on the dashboard server. `viewer_scene.json` combines a 240 × 240 display mesh, modern water features and **D8 contributing-area screening** computed on 2,160 × 2,160 native terrain cells. Each display cell aggregates 9 × 9 native cells: mean elevation and maximum contributing area. The display mesh is approximately 270 m; it must not be mistaken for finer terrain information.

The D8 calculation routes each cell to its steepest lower neighbour using approximate local metric distances and a constant pixel-area contribution. No depression filling or flat routing is applied; local sinks retain their contributing area. A numerical conservation check verifies that total area at terminal sinks equals domain area. Rainfall, runoff coefficients, hydraulic controls, canal conveyance, storage and bacterial processes are absent. Upstream areas outside the rectangle are omitted. The top-ranked cells are **terrain-screening candidates**, not predictions of discharge, water depth, contamination or bacterial concentration. Their locations are sensitive to DSM artefacts and the unresolved sinks.

For actual model output, import a WGS84 Point/LineString GeoJSON FeatureCollection in the viewer with `model.name`, `model.scenario`, `model.metric`, `model.unit` and a finite `properties.value` for every feature. See `/model_output.schema.json`. Files stay in the browser; imported values are displayed as user-supplied and unverified, with their declared metric and unit. Nothing is uploaded or substituted for a calibrated simulation.

## Reproduce

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r scripts/requirements-gis.txt
.venv/bin/python scripts/acquire_context.py
.venv/bin/python scripts/build_viewer_scene.py
python3.12 server.py --port 9090
```

Run from the repository root. The acquisition script reuses existing TIFFs and acquires the dated Geofabrik extract if absent. Preserve `provenance.json` and downloaded source files together. Dependencies are needed for data preparation, not for the webserver.

## Still needed

Separately authorized georeferenced KALC/CALI bare-earth DTM or classified point clouds; original archaeological GIS with feature IDs and phases; surveyed channel sections and control levels; storage curves; hydraulic forcing and calibration data. The credentialed Archaeoscape benchmark cannot supply a spatially aligned terrain layer under its published no-localization terms.

## TOPSAR update — 6 November 2026

A separate TOPSAR selector now provides a ~5 m display tile around Angkor Wat and an ~80 m full-strip display. Source coordinates are converted using the documented AIRSAR SCH operation; this is no longer merely a raw-file candidate. The preview remains provisional for ground accuracy, mask interpretation and hydraulic use. TOPSAR screening is intentionally disabled. See [conversion details](topsar/CONVERSION.md) and [processing provenance](topsar/conversion_provenance.json). The earlier raw inspection and search report are retained as acquisition-stage records.
