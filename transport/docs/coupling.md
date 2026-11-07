# Saved hydraulic interval coupling

`simulate(config)` accepts a `hydraulic_result` object containing the saved
hydraulic network, node/edge IDs, external flows and samples. It uses each ending
sample's `preceding_interval_mean_flows_m3_s`, never the instantaneous discharges,
to evolve storage and mass over that interval. Initial and final hydraulic storage
must match these fluxes in every cell. Positive storage is required throughout.
The adapter calls the existing biological or chemical reaction module through the
transport core. Final mass, boundary inputs/exports, reaction terms, water volumes
and per-interval water residuals are reported separately.

`boundary_concentration` is a scalar or node-ordered vector; it defaults to zero.
Optional `edge_transport` entries keyed by edge ID supply dispersion/diffusion
parameters (`area_m2`, `distance_m`, `dispersion_m2_s`,
`molecular_diffusion_m2_s`). The saved signed flows always determine advection.
`dt_max_s` controls transport substeps and `max_steps` caps the aggregate run.
Hydraulic times determine duration and output intervals.

Run `/tmp/qmodel-gis-env/bin/python scripts/build_current_transport.py` to reuse
the saved hydraulics and write both conservative examples plus a source-hash
manifest under `assets/data/transport/`. The workbench's “Load current hydraulic
scenario” loads the selected model's runnable configuration; “Run transport” uses
the existing `/api/transport/simulate` endpoint.

The unit tracer is arbitrary, with no inferred archaeological contamination.
Reaction coefficients remain unset and processes disabled in these examples.
Interval means preserve volume but cannot reconstruct reversals within an output
interval; finer saved hydraulics are needed to assess that error. Positive mass
and conservation are numerical checks, not field validation. These terrain
candidates do not model either baray, and their geometry and forcing are uncalibrated.
