# Regional fixed-terrain water-system rebuild

The supplied `knowledge/Fixed-terrain model/pilot.png` and `full model.png` show different things. The pilot is a locally initialized, boundary-driven 900-second experiment. The former regional default was a 30-second low-water/rainfall startup, with sparse representative face glyphs. It was not a regional reproduction of the pilot. Presenting it as the next version of that flow network was wrong.

## Construction errors corrected

1. **Water initialization.** Using the minimum terrain elevation of a whole connected mapped-water component plus 0.10 m dried almost all of the pilot's waterways. Canals can connect storage areas at different elevations, so their global minimum is not a suitable regional starting water level. The corrected scenario initializes each pond/moat polygon component independently and uses configurable local cross-section-derived water surfaces on conduits outside storage polygons. This is an explicit hypothetical starting condition, not inferred ancient water levels.
2. **Forcing and time.** Rain on almost-dry ground and a closed perimeter did not reproduce the pilot's imposed inlet-stage hydrograph. The corrected case removes rain-film forcing. It is a 60-second **water-present relaxation experiment**, with no external inflows. It is still not the same forcing as the pilot and is not a flood or drought prediction.
3. **Network delivery.** Sampling raster face arrows did not extract reaches. The rebuild supplies centerlines, branch/end nodes, component IDs, source lineage, storage polygons, channel/storage contacts and a GIS GeoPackage. The native 2D raster remains the hydraulic calculation; the reach graph is a derived inspection/export product, not a replacement 1D solver. Newly flooded overland paths can connect mapped components outside this conduit graph; inspect the native depth/face output for those exchanges.
4. **Display.** The default overview now shows extracted reach geometry rather than a scattering of representative cell-face arrows. All native faces and the actual 0.5 m cell grid remain inspectable at close zoom. Optional representative overview glyphs are explicitly labeled.

## Geometry and connectivity

Mapped canals, moats and buffered water traces are rasterized on the source's native EPSG:32648, 0.5 m grid. Skeleton thinning supplies candidate conduit centerlines; every skeleton edge is traced once. Branches and loops are retained. Diagonal pixel contacts without an orthogonal mapped-water route do not become connections in the four-face hydraulic grid. Short branch connectors are retained rather than pruned into broken topology. Long traces are subdivided at approximately 100 m, with shared endpoints. Geometry simplification is at most 0.25 m.

Ponds and reservoirs stay as storage polygons; there are no reservoir-centroid spokes or proximity links across missing ground. Moats are retained as both conduit inspection geometry and resolved storage areas. A contact port means a mapped conduit actually intersects a storage boundary. It is a candidate exchange location, not a verified sluice, open bank or spillway. Its nearest reach association is diagnostic, not an added hydraulic edge.

**Geometric connectivity is not hydraulic connectivity.** Two native cells exchange water through their shared face when water is above the higher adjacent bed elevation; the pressure gradient and friction determine signed flux. Resolved banks remain in the terrain. Rising water can activate additional faces and outlets anywhere along a bank. No erosion, automatic terrain lowering, sink filling, gap merging or artificial single outlet is imposed. Real culverts, buried channels and missing bathymetry still require evidence and explicit scenarios.

## Corrected scenario

See `configs/water_system.json`:

- Storage initial stage: each polygon part's valid terrain 25th percentile + 0.15 m.
- Conduits outside storage: local cross-section terrain 25th percentile + 0.15 m, sampled every 10 m along reaches and interpolated to native cells. High banks remain dry.
- Rainfall and infiltration: zero in this diagnostic.
- Terrain: unchanged native 0.5 m elevations. Impermeable no-data cells and closed external perimeter.
- Hydraulic duration: 60 s. Up to 40 threads; fixed terrain, local-inertial momentum with fully implicit quadratic Manning friction.
- Conservative unit tracer: numerical routing/conservation diagnostic only.

Adjust `initial_stage_percentile`, `initial_stage_offset_m`, `conduit_bed_percentile`, `conduit_stage_above_bed_m`, `conduit_stage_station_spacing_m`, `manning_n`, `duration_s`, and the existing evidence-labeled `initial_water_levels`/`terrain_modifications` arrays. Water-trace buffer width, maximum reach length and line simplification are explicit extraction settings. Changing an initial water level is not a sustained stage boundary. The regional native engine still rejects unsupported stage-boundary and groundwater options.

These modern mapped geometries are candidates for archaeological reconstruction. A wetter-looking map alone does not confirm ancient channels, flow rates or contaminant hotspots. Broad source polygons can include banks; water surfaces must be distinguished from uniform depths. A rejected constant-depth conduit trial is preserved separately. Cross-section stages are still hypotheses and can produce transient drainage. Review the water levels and bed/crest elevations before interpreting directions. Local-inertial momentum omits advective acceleration; high-Froude faces require a different solver/regime review.

## What is exported

Local, restricted derivatives under `assets/private/water_system/`:

| Artifact | Meaning |
| --- | --- |
| `water_network.gpkg` | EPSG:32648 reaches, nodes, waterbodies, contacts; cross-sections after hydraulic coupling |
| `reaches.geojson` | WGS84 candidate centerlines with endpoint references and source feature IDs |
| `nodes.geojson` | Native pixel-center locations, degrees and geometric component IDs |
| `waterbodies.geojson` | Separate pond/reservoir/moat polygon parts |
| `ports.geojson` | Geometric channel/storage contacts with unverified crest status |
| `cross_sections.geojson` | Three inspection cross-sections per reach, where constructible |
| `hydraulics/final.tif` | Native 0.5 m depth, east/south unit-width fluxes, unit tracer and face velocities |
| `hydraulics/initialization.json` | Assumed per-storage stages, water volumes and interpretation |
| `network_verification.json`, `hydraulics/verification.json` | Automated geometry/export/conservation checks, distinct from site validation |

The viewer provides the GeoPackage and native output downloads. At cell zoom, **Export visible 0.5 m cells** creates a GeoJSON with actual 0.25 m² cell polygons, depth, bed, stage and signed face discharges. Exports are limited to 10,000 cells per viewport; the full native raster provides whole-domain GIS access.

Cross-section discharge is integrated from staggered east/south native fluxes at spacing no larger than 0.5 m. Positive values follow `from_node` to `to_node`. A directed reach requires matching non-negligible signs at three sections; dry, unresolved and mixed-direction cases remain labeled separately. Even three matching sections do not prove continuous hydraulic passage between them. These are transient 2D-derived estimates, not calibrated steady 1D discharges.

## Review in the dashboard

Open `/regional-terrain`, use **Inspect original pilot area**, and compare water depth with the satellite image and hillshade. Use **Zoom to 0.5 m cells** for individual face directions and native-cell values. At regional scale the map cannot display every half-metre cell on one screen; the reach overlay supplies the readable network overview. Reservoir interiors are 2D storage, so a tree of lines across a lake would be misleading.

Check: missing mapped channels; false polygon contacts across banks; channels interrupted by elevated native bed cells; stage-sensitive multiple outlets; and actual source coverage. Retain disconnected features as QC evidence. The source covers approximately 93 km², not the whole Greater Angkor region; do not infer coverage from the satellite basemap.

## Reproduction

Use the durable `qmodel` environment, including `scripts/requirements-native.txt` and `scripts/requirements-reports.txt` alongside the GIS requirements. Do not overwrite a completed hydraulic case to test a different water-level hypothesis.

```bash
python scripts/build_water_network.py
python scripts/verify_water_network.py
python scripts/build_conduit_stages.py
python scripts/preflight_water_case.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=40 python scripts/build_regional_native.py \
  --config configs/water_system.json --output assets/private/water_system/hydraulics
python scripts/finalize_water_system.py
```

The earlier rain startup remains preserved under `assets/private/regional_native/` for diagnosis.

## Method references

- [scikit-image skeletonization documentation](https://scikit-image.org/docs/stable/auto_examples/edges/plot_skeleton.html): skeleton thinning preserves shape topology; it does not identify a surveyed thalweg or establish hydraulic continuity.
- [HEC-RAS 2D mesh development](https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.5/development-of-a-2d-or-combined-1d-2d-model/development-of-the-2d-computational-mesh): hydraulic mesh construction and terrain controls require separate attention. This custom native raster solver is not HEC-RAS and has not acquired HEC-RAS validation by analogy.
- Penny et al. (2018), local manuscript and supplement in `assets/manuscripts/`: the published abstracted infrastructure network is a different representation from native resolved 2D water storage and face exchange. It is a useful archaeological comparison, not a target image to reproduce by inventing links.
