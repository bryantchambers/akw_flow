# Regional versus original fixed-terrain pilot — 12 November 2026

## Findings

The regional grid covers the full supplied survey at 0.5 m, but the saved regional run is **not an extension of the original pilot's forced event**. Both rendering and scenario differences caused the mismatch.

### Rendering gap, now corrected

The original regional viewer sampled a fixed 20 × 28 array of locations, rejected samples below 1 mm cell depth, and combined sampled face velocities into glyphs. Narrow wet channels and moving faces beside dry cells were easily missed. It did not provide native face/grid inspection or the pilot's network-style display.

The corrected display selects actual signed native face discharges. At overview zoom, it retains the strongest real face separately in each orientation per display bin. Coordinates and signs remain those of that native face; no flows are summed, invented, or linked between distant feature anchors. At cell zoom, all qualifying native faces are returned for the bounded viewport, with native grid lines and optional inactive faces. Arrowheads follow the sign of the discharge between the two adjacent cell centres.

On the saved outputs, the old display produced 2 sampled vectors over the full footprint versus 1,208 representative native flowing faces with the new display. For the exact pilot bounds it produced 3 sampled vectors versus 560 representative faces. Counts vary with viewport, threshold and display density; they are not counts of all hydraulic connections.

A separate native data check found 8,574 east/south faces exceeding 10⁻⁵ m³/s within the pilot crop. Those faces existed in the result; the previous point sampler was a poor way to visualize them.

### Scenario gap, still requiring a new hydraulic case

| Property | Original fixed-terrain 2D pilot | Current regional native run |
|---|---|---|
| Computational spacing | 10 m, subgrid terrain | 0.5 m native cells |
| Saved end time | 900 s | 30 s |
| Initial water setup | Local mapped-terrain 25th percentile + 0.15 m | Connected mapped component's minimum terrain + 0.10 m; higher terrain dry |
| Boundary forcing | Northern stage rises 1.5 m, holds, then recedes | Closed perimeter; no inlet hydrograph |
| Rainfall | 0 | 30 mm/hour |
| Initial water volume in pilot crop | 14,941.95 m³ | 60.04 m³ |
| Final water volume in pilot crop | 20,109.29 m³ | 162.44 m³ |

The prototype's pumped boundary event cannot be compared directly with the regional startup case. Most of the moat/channel network starts much drier regionally. This cannot be repaired by making more arrows appear. Native and coarse cell storage/wet-area definitions also differ; this is a diagnostic comparison, not a mesh-convergence test.

The existing native solver rejects prescribed stage boundaries. A comparable regional event therefore needs a boundary-forcing implementation, reviewed regional initial levels, appropriate inlet/outlet locations and a sufficiently long simulation. Copying the pilot's boundary stage to an unrelated regional edge would not define an equivalent event. Available water levels and bathymetry are still hypothetical/unverified.

## How to inspect

Open `/regional-terrain` and refresh the page to load the new controls.

1. Click **Network-style view**. Mapped channels/waterbodies stay visible; imagery, terrain and raised-feature clutter are hidden. Orange arrows are computed native flows, not mapped-channel assumptions.
2. Click **Inspect original pilot area**. Read the same-footprint comparison beside the map.
3. Click **Inspect a displayed flowing face** to centre a real active face and zoom to 0.5 m cells. Alternatively, pan to a site and choose **Zoom to 0.5 m cells**.
4. Turn **Native cell grid** and **Include inactive faces at cell zoom** on/off. Grey faces can be stationary, dry, blocked or below the chosen display threshold; they are not asserted to carry water.
5. Adjust **Minimum native face discharge** if investigating weak flows. Values are per 0.5 m face and are not directly equivalent to discharge across a 10 m pilot interface. Weak settings include thin rainfall films outside the intended slow, deeper-flow interpretation.
6. Toggle **Original 10 m pilot reference** for a purple overlay at the saved pilot end time. Purple reference fill/arrows are from another simulation; they are not native regional results. Switch it off to inspect regional output alone.
7. Use **Layered view** to restore satellite and native terrain. Source outlines remain visible even when their waterways are dry in this scenario.

Native raster data remains 0.5 m. Display tiles above zoom 22 are enlarged from that display level; the grid and clicked values still refer to real 0.5 m solver cells. Not all 372 million faces can be rendered simultaneously at regional scale; representative overview glyphs and exact local inspection are explicit modes.

## Rebuild and provenance

```sh
mamba activate qmodel
python scripts/build_regional_face_index.py
python scripts/build_regional_view_comparison.py
python scripts/restart_dashboard.py
```

The display index is under `assets/private/regional_native/faces_*.tif`, with source size/mtime in `face_index.json`. Queries reject a stale overview index. `view_comparison.json` records source states for both simulations; the API marks it stale if either changes. Future native builds create their face index and, if the pilot exists, the comparison after numerical/export work.

No numerical simulation, starting level, discharge, source terrain, or raw GIS dataset was altered during this review. These are inspection derivatives. They remain private and ignored by Git; HTTP exposes only the allowlisted inspection responses.

## Verification

109 tests passed, including signed face selection, preservation of native row/column identity, partial/no-data blocks, native face width, inactive-face handling, stale-index rejection and no fictional initial velocities. Browser checks passed for regional and pilot views, reference overlay, native cell zoom, weak-flow/idle controls and a 390 px viewport, with no JavaScript errors.

The renderer fixes improve access to existing numerical results. They do not validate regional flood/drought behaviour, submerged geometry, or contaminant/bacterial hotspot predictions.
