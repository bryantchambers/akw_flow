# Prescribed-flow environmental transport

`transport.core.simulate(config)` solves one constituent at a time in completely mixed water control volumes and associated immobile bed inventories. It accepts biological viable-count equivalents or chemical mg. It is an exploratory finite-volume solver, not a calibrated reconstruction of Angkor water quality.

For water mass M_i = V_i C_i:

`dM_i/dt = sum(upwind advective inflows - outflows) + sum(K_ij (C_j-C_i)) + loading_i + reaction_water_i`

`K_ij = (molecular_diffusion_m2_s + dispersion_m2_s) * area_m2 / distance_m`

`dB_i/dt = reaction_bed_i`

Advection and dispersion use equal/opposite internal edge fluxes. Diffusion and unresolved longitudinal mixing are separately configurable. Lateral/vertical mixing within each control volume is instantaneous; transverse spatial gradients require subdividing the domain. Positive boundary flow enters the system and requires a concentration. Negative boundary flow exports the current cell concentration. There is no implicit upstream concentration or source.

Cells require unique IDs, positive `volume_m3`, optional `bed_area_m2`, and optional GeoJSON geometry. Connections name `from`, `to`, signed `flow_m3_s`; diffusivity requires explicit exchange area and distance. All units use SI; biological concentrations are viable-count/m3 and chemical concentrations mg/m3 (divide by 1000 for mg/L). Initial bed values are inventories, not concentrations. `loading_per_s` is direct constituent addition, without added water.

Default fixed volumes require per-cell water balance. Set `dynamic_volumes: true` for `dV/dt = sum(inflow)-sum(outflow)` with prescribed flows. This does not solve a momentum equation or update stage-dependent flow itself; hydraulic time series must drive the successive intervals. Drying to zero volume, wetting, shocks and full Saint-Venant hydraulics are outside this transport routine.

The explicit Euler integrator limits each step by outgoing advection and exchange conductance, and by loss of water mass, bed mass and water volume. It does not silently clip negative inventories. `dt_max_s`, `max_steps`, `duration_s`, and `output_interval_s` are configurable. This first-order method introduces numerical dispersion and requires grid/time-step convergence checks; stiff reactions may exceed the step limit. Reported mass residual compares final water+bed inventory with initial inventory, boundary and local inputs, biological production/atmospheric input, boundary export and irreversible loss/atmospheric export. Chemical parent loss does not imply mineralization.

EPA's [WASP overview](https://www.epa.gov/hydrowq/water-quality-analysis-simulation-program-wasp) supports coupling transport and kinetics to hydrodynamics. This implementation is independent and is not EPA WASP or EPA-validated software. Species/chemical source tables and kinetic limitations are documented separately.

Run `python scripts/run_transport.py CONFIG.json --output RESULT.json --geojson VIEWER.geojson`. The viewer export includes actual supplied cell geometry only. No invented geographic source locations or defaults are added. Default coefficients disable reactions until a user supplies applicable measured or otherwise justified rates; this is a conservative scenario, not a survival prediction.
