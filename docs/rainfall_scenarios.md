# Rainfall sensitivity screen

The first sweep uses six independent **10-minute** constant-intensity rainfall events over the supplied approximately 93 km² native 0.5 m survey grid. It is an end-of-event sensitivity experiment, not an observed monsoon or a design-return-period flood.

| Rainfall intensity | Duration | Accumulated rain |
| --- | --- | ---: |
| 0 mm/h, control | 10 min | 0 mm |
| 5 mm/h | 10 min | 0.83 mm |
| 15 mm/h | 10 min | 2.50 mm |
| 30 mm/h | 10 min | 5.00 mm |
| 60 mm/h | 10 min | 10.00 mm |
| 100 mm/h, stress case | 10 min | 16.67 mm |

The user selected the 10-minute screen before hour-long storm simulations. It is distinct from the existing 60-second, zero-rain GPU reference. Each rainfall case is compared against the new zero-rain control at **the same 600-second duration**, so continued drainage of the assumed initial water is not mistaken for a rainfall response.

## Controlled assumptions

Every case starts afresh from the same cross-section-derived conduit stages and independent storage levels. Roughness, terrain, initial tracer, numerical precision, dry-depth threshold and CFL policy are fixed. Rainfall is spatially uniform. Infiltration is explicitly zero: a saturated/no-infiltration upper-runoff bound, not a measured soil parameter. The perimeter remains closed, with no upstream river inflows, groundwater coupling, erosion or evolving channel geometry.

Higher rainfall therefore adds more water, but individual reach discharges or direction classes need not change monotonically. Storage, overbank redistribution, pressure gradients and competing paths can change direction or redistribute flow. The solver's local-inertial approximation remains subject to its high-Froude warning.

Source context: Lustig et al. discuss regional archaeological flood mechanisms including a hypothetical storm delivering 50–60 mm within an hour. Their site focus is Koh Ker, and the discussion does not provide a return-period design curve for this Angkor grid. We use it only to motivate a strong-storm sensitivity range. The 100 mm/h member is explicitly a stress case. See [Lustig et al. (2018)](https://doi.org/10.1016/j.jasrep.2017.11.014), already held in `assets/manuscripts/lustig_2018_breakdown_angkorian_hydraulic_system.pdf`.

A monsoon is a seasonal regime, not a single intensity category. Later monsoon experiments require longer or repeated storm sequences, justified antecedent water levels, rainfall timing/spatial patterns, soil/infiltration sensitivity and appropriate external river/lake boundary conditions. This screen does not establish historical or seasonal conditions.

## Results and comparisons

Each case retains its own initial/final rasters, configuration, executed-source snapshots, native checks, GeoPackage, reach/node/storage/contact layers and cross-sections. The main GPU reference and its network are not overwritten. Cases become selectable only after native verification, coupling and summary production complete.

In `/regional-terrain`, use **Rainfall scenarios → Verified result to inspect**. Pending cases are disabled; the batch panel reports progress separately from the selected saved result. Satellite imagery, hillshade, native depth, network geometry and cell-face output remain independently inspectable with the same colour scales and opacity controls.

The reach-change colours mean:

- Green: three-section direction consistency exists in the selected case but did not exist in the control. This is not necessarily a previously dry reach.
- Purple: the consistent direction is reversed relative to the control.
- Orange: a consistently flowing reach in the ordinary display class.
- Grey: a formerly consistent direction is no longer established.

Geometry is fixed. These colours do not mean new archaeological channels were discovered. Tooltips include signed mid-section discharge and its difference from the control.

The scenario summary reports final-snapshot areas with depths at least 1 mm, 1 cm, 5 cm and 10 cm; depth differences; newly qualifying/reversed native faces; and reach changes. Native-face statistics require both a discharge threshold and a minimum predictor face depth, so microscopic rain-film velocities do not dominate the comparison. Counts of newly flowing faces are **not counts of spillway structures or discrete outlets**. Inspect the native terrain/stage/face layers to investigate candidate additional outlets. Genuine bank crests and structures still need evidence.

Blue at the 1 mm display threshold can include ordinary shallow rain film. Use the deeper area thresholds and channel fluxes before describing a change as substantial inundation. Maps and statistics are end-of-event snapshots, not cellwise maximum-depth or peak-inundation maps over the whole event. Unobserved intermediate outlet activation can be missed.

## Operation and provenance

```bash
# Prepare frozen per-case configurations and submit one sequential A100 job.
python scripts/submit_rainfall_scenarios.py

# After an interruption, resume completed members and archive/restart the partial member.
python scripts/submit_rainfall_scenarios.py --resume <suite-id>
```

The launcher uses Slurm, one A100 on `dandygpun01fl`, up to 40 CPUs, 96 GB host RAM and a 12-hour limit. Environment checks/installation occur on the allocated A100. The job exits when the six members finish. Full native 600-second cases remain computationally substantial; expect several hours for the batch, with shared-cluster timing variability.

Configuration: `configs/rainfall_scenarios.json`. Each event has an independent case JSON under `assets/private/water_system/rainfall_suites/<suite-id>/`. Results live under `assets/private/water_system/hydraulics_gpu_<suite-id>_<rain-id>/`; networks are inside each case's `network/` directory. The suite catalog and progress are recorded in `suite.json`; the final tabular comparison is `comparison.csv`. These restricted derivatives remain local and ignored by Git.

The pipeline checks that initial water volumes match and that integrated precipitation equals intensity × duration × valid area. It runs native export/conservation checks before coupling and comparison. Numerical source hashes are recorded, and source changes stop the batch rather than silently mixing numerical versions. Completed cases survive interruptions; a partial case must restart from its initial conditions because live GPU timestep checkpoints are not yet implemented.

The live catalog is `/api/rainfall-scenarios/status`. Selected-case raster, face, point, network and download requests carry the same `case` identifier. Per-case query validation and caches prevent another case's reach discharges being paired with the selected raster.
