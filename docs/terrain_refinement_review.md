# Bank and mesh review — 10 November 2026

## What is available

The channel inspector now includes a **Bank and mesh review** panel and two saved comparison models:

- **Study · matched 10 m pilot**: 4,096 cells, 8,064 faces.
- **Study · refined 5 m pilot**: 16,384 cells, 32,512 faces.

The original pilot remains intact. The study models are read-only in the browser; rebuild them with:

```sh
/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python scripts/build_terrain_refinement.py
```

`--reuse` recomputes screening, diagnostic transects and comparison maps from the saved runs after checking scenario and source-file state. It does not rerun hydraulics. To change hydraulic geometry, forcing, the solver or initialization, rebuild without `--reuse`.

All study inputs/outputs are local under ignored `assets/private/terrain_refinement/`. The server exposes only the named dashboard derivatives, not raw survey data or numerical mesh files.

## A fair comparison

Both runs use the same native terrain footprint, roughness, duration, prescribed stage hydrograph and 10 m wide northern inlet band at the mapped canal ANG_F_09042. Native initial water volumes are integrated over mapped water pixels and aggregated to either mesh. Initial total volume differs only by floating-point rounding (5.5e-12 m³).

This differs from the original pilot, whose stage-based initialization can wet an entire partly mapped cell, and whose north-boundary selection can include unrelated ponds. The matched study uses one fixed inlet band to isolate the canal experiment. Compare the two **study** models to each other, not the original pilot to the 5 m model.

The boundary cells prescribe stage over different cell lengths in the two meshes. This is a common simplified forcing convention, not an exact external-boundary Riemann condition. Its discretization contributes to the sensitivity measured here. Both runs retain 32 storage quantiles per cell, so spatial topology and storage-compression effects are combined. A two-resolution comparison does not establish grid convergence.

## Results

| Measure | Result |
|---|---:|
| Final mean-depth RMSE across all parent cells | 4.07 mm |
| Final mean-depth RMSE over wet union | 7.16 mm |
| Largest local final mean-depth difference | 64.24 mm |
| Agreement in final wet/dry parent-cell support (>1 mm mean depth) | 99.46% |
| Final total water storage, 10 m | 20,065.34 m³ |
| Final total water storage, 5 m | 19,726.53 m³ |
| Difference in net water admitted under prescribed stage | −338.82 m³ |
| Canal transect cumulative signed flow, 10 m | 904.70 m³ |
| Canal transect cumulative signed flow, 5 m | 811.61 m³ |
| Peak sampled absolute transect discharge, 10 m | 3.460 m³/s |
| Peak sampled absolute transect discharge, 5 m | 3.084 m³/s |

Water and unit-tracer budgets close to numerical precision in both runs. Different admitted water volumes are hydraulic responses to stage forcing, not conservation errors. The canal transect is a diagnostic section at projected northing 1,483,800.303 m, across easting 376,559.663–376,709.663 m. It is not a surveyed outlet. Its cumulative flow differs by approximately 10.3%; similar-looking depth maps therefore do not establish equivalent routing.

Differences are computed on the 10 m parent grid by conserving the four child-cell water volumes. Fine tracer concentration is water-volume weighted. Local fine-cell peaks are not retained by that aggregation. No bacterial rates, contaminant sources or calibrated hotspot predictions are included.

## Native-terrain screening

For each cell, native 0.5 m terrain is tested at three uniform water levels: 20.596, 21.346 and 22.096 m (provisional vertical units/datum). Four-neighbour wet-pixel connected components are counted; components smaller than 1 m² are excluded. A cell containing multiple components can mix disconnected pools prematurely because the solver assigns one stage per cell.

This is a screening flag. A component can connect around the cell outside its boundary; small terrain irregularities or uncertain bathymetry can also create flags. These levels are diagnostic, not necessarily simulated local water levels. Centre cross-sections can miss off-centre ridges, so inspect the imagery, mapped banks and wider terrain too.

| Screening result | 10 m | 5 m |
|---|---:|---:|
| Cells flagged at any screening level | 232 | 213 |
| Flagged cells that become wet in the run | 49 | 49 |
| Flagged cells intersecting mapped banks/raised features | 49 | 24 |
| Secondary-pool area at highest screening level | 684.0 m² | 284.5 m² |

Raw cell counts have different denominators and cell areas. The smaller secondary-pool area on the fine mesh is encouraging but does not prove bank connectivity is correct. Rankings put simulated-wet flags first, then mapped-barrier overlap, then secondary-pool area. This is a review order, not a calibrated error score.

## How to inspect

1. Open `/channel-inspector`. In **Bank and mesh review**, click **Load 10 m / 5 m comparison**. This loads the matched 10 m run, summary and canal flow chart.
2. Enable **Show possible unresolved barriers / pools**. Red outlines intersect mapped banks or raised features; amber outlines have split native pools without those mapped overlaps. Magenta highlights the selected queue item. These are review annotations, not modelled flow paths.
3. Choose a queue item. The map zooms to it and shows native west–east and north–south centre profiles. Its description states whether it gets wet during the run. Check source features and terrain before making a geometry decision.
4. Enable **Overlay depth difference** and scrub time. Pink means deeper on the 5 m mesh; blue means shallower. The overlay shows fine-volume averages on the 10 m grid, not raw fine depths. It is shown only for the matched study models.
5. Switch to **Study · refined 5 m pilot** to inspect actual fine-cell depths and face flows. The same review controls now inspect the fine mesh. Use **Load / zoom to flow** to return from a close cell inspection to the whole pilot.
6. Focus first on wet flagged cells near mapped banks, inlet transitions, and the moat edge. Decide whether a cross-cell ridge needs mesh alignment or a documented fixed face profile. Preserve plausible openings. Do not automatically raise every flagged face or burn all mapped waterways.

## Decision and next gate

The finer mesh is available for exploration, but the comparison does **not** clear regional hydraulic rollout or hotspot interpretation. Next implement targeted bank-aligned refinement or verified face controls at the wet review locations, and test outlet/overbank fluxes against a benchmark or established hydraulic solver. A third resolution and storage-compression check will help distinguish numerical effects. Source vertical metadata, submerged geometry and actual forcing remain unverified.

No bank elevations were changed automatically. No erosion or sediment processes were added. The source surveys, original pilot, and original regional graphs were preserved.

## Verification and method reference

82 unit tests passed, including synthetic internal-bank splitting, diagonal-contact exclusion and conservative nested-grid aggregation. Chromium checks covered comparison loading, cell queue, profiles, both meshes, difference overlay, time changes and a 390 px mobile viewport; no JavaScript errors occurred.

USACE recommends refinement regions and bank/terrain breaklines to capture important hydraulic features. Our uniform refinement is a sensitivity study, not an equivalent bank-aligned mesh: https://www.hec.usace.army.mil/confluence/rasdocs/rmum/latest/geometry-data/2d-flow-areas
