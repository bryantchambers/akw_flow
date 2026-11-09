# Huma-Num preliminary channel dataset

## Source and outputs

Input: independently supplied Huma-Num `2026_06_17_danish_eDNA` package, not the anonymized Archaeoscape release. Its DTM and mapped features are in projected UTM coordinates. Do not match Archaeoscape parcels against this data.

All source and derived spatial data stay inside ignored, HTTP-blocked `assets/private/`. Derived outputs are in `assets/private/humanum_channels/`. Redistribution permissions have not been established.

The QGIS project's category labels identify 67 canal polygons, 8 water line features, 4,690 ponds, 242 pond banks, 126 temple moats and 789 raised linear features. The inventory preserves original FIDs, TYPE and all source attributes. Labels are source classifications, not newly verified hydraulic connections. Unmapped codes are retained in a QC list, not interpreted. Polygon parts are retained as source rings; no new ring topology is inferred.

## First extraction

```bash
/tmp/qmodel-gis-env/bin/python scripts/build_humanum_channels.py --config configs/humanum_channels.json
```

The configurable pilot is 512 x 512 pixels (256 x 256 m) anchored near the mapped canal closest to the configured Angkor Wat target. It is not extraction of the entire 93 km² raster rectangle, nor a catchment boundary. The exact selected source feature, raster window, relevant source hashes and processed-window hash are recorded in `channel_dataset_manifest.json` and each network.

Output files:
- `mapped_water_features.json`: source classifications and original IDs, ring/line parts in EPSG:32648.
- `sensitive_network.json`, `balanced_network.json`, `conservative_network.json`: independent candidate graphs with lengths, provisional terrain slopes, contributing areas and local depression.
- `channel_dataset_manifest.json`: profiles, coverage, provenance, limits and per-link profile membership.
- `pilot_comparison.svg`: source canal/water/moat outlines in blue, terrain candidate links in red; three aligned north-up local panels.

The first run produced 2,820 / 124 / 4 short D8 cell links in the three profiles. These are not channel counts. The raw pilot has 9,589 terminal routing cells (pits, flats or edges). Its contributing areas are truncated at window boundaries and local sinks. Strict-downhill routing does not imply an observed or ancient discharge direction. No unseen connections are fabricated.

## Tuning

Edit `configs/humanum_channels.json`: contributing-area threshold, local relative-depression threshold, Gaussian smoothing sigma, relief-neighbourhood radius, minimum downhill slope, minimum connected length and manually excluded raster cells. Current profiles vary contributing-area thresholds 10/50/200 m² and local depression thresholds 0/0.01/0.05 m. Component length is total link length in a graph component, not longest-channel length. Profile agreement is persistence under chosen settings, not statistical confidence or age.

Lower thresholds can capture weak traces and also vegetation-filtering artefacts, noise and modern features. Current settings are exploratory, not calibrated archaeological detection. Smoothing can remove faint banks; zero is the default. Raising a minimum slope can remove long shallow channels. No pit filling/breaching, labels-based burning or automatic gap connections are applied. The inventory is not burned into the DTM, so disagreement remains visible.

Metres are provisionally assumed for elevation scale, while horizontal metre units are verified from the projected CRS. The TIFF does not specify elevation units/vertical datum. Unknown widths and bed depths stay null. No calibrated hydraulic simulation is generated from these candidate graphs.

## Next acceptance gates

1. Visually review candidate overlap, false positives, missed mapped canal sections and source TYPE interpretations.
2. Confirm vertical units/datum, acquisition/processing history and terrain accuracy.
3. Resolve selected flats/depressions with documented scenario-specific conditioning; preserve raw vs altered surfaces and modification limits.
4. Expand with buffered tiles, explicit boundary inflows and reviewed graph merging. Pilot extraction cannot establish the regional topology.
5. Extract and review cross-sections; distinguish present surviving terrain from reconstructed beds, structures, reservoirs and historical periods.
6. Only then assign uncertain geometry/roughness and run hydraulic/transport ensembles.

## Dashboard channel inspector

Run `python scripts/build_channel_inspector.py` with the GIS environment to build five private inspection derivatives. `/channel-inspector` combines Esri World Imagery, mapped Canal and Water outlines, elevation and local-depression rasters. The dashboard and existing 3D viewer link to it. Each layer has independent visibility and opacity controls. Feature selection reports source IDs.

The regional terrain image is downsampled to approximately 15 m display spacing. The native-spacing 512-pixel pilot displays about 0.5 m. The imagery layer is limited to available level-17 native tiles and enlarged at closer zooms; imagery resolution is independent of terrain resolution. Local depression uses neighbourhood mean minus elevation and is NOT measured bathymetric or water depth. Its neighbourhood size changes with preview resolution and is disclosed in the UI. Display colour ranges are percentile-clipped and displayed; original values are not overwritten.

The server permits only `inspector.json` and four named PNGs through `/api/channel-inspector/`. Raw private assets, other derivatives, Archaeoscape files and tokens remain blocked. This is explicitly selected data exposure for the requested local inspection view, not authentication: any person able to reach port 9090 can view these derivatives. Do not expose or publish the service beyond the authorized research audience without appropriate permission/access controls. Data remain excluded from Git.

Leaflet 1.9.4 is vendored with its licence; imagery is requested directly from Esri, with attribution. Browser QA checked 67 canals, 8 water traces, opacity/visibility controls, terrain switching, imagery and raster loading, desktop/mobile layout and no JavaScript errors. Actual satellite imagery was visually checked at the native-detail view.

## Complete mapped water-feature scope

The inspection view now loads all mapped water-related classes: Canal (67), Water (8), Temple Moat (126), Pond (4,690), Pond Bank (242). All five start visible, with separate opacity controls. Raised Linear (789) is an optional potential-barrier evidence layer; its hydraulic function is unverified. These source classes are not a guarantee that every historical water feature was mapped.

The source inventory assigns candidate roles (conveyance, storage, mixed moat storage/conveyance, bank/barrier), preserving unassigned connectivity, unknown chronology and unset bed depth, water level and cross-section. Adjacent polygons or intersecting lines do not automatically establish a hydraulic junction. Source parts remain intact; polygon holes and storage areas need topology review before assigning volumes. Floodplains, overflow routes and unmapped ditches require terrain interpretation. Regional reservoirs and structures remain explicit coverage/completeness questions.
