# Regional source-feature graph and preliminary hydraulic cells

## Reproduce

Use the GIS environment and `python scripts/build_regional_network.py --config configs/regional_network.json`. Install GIS requirements first. The source dataset must already be present under the private Huma-Num folder. All outputs remain ignored under `assets/private/regional_network/`. The server only exposes explicitly named inspection derivatives; raw source files remain blocked.

This supersedes the *extent* of the pilot, not its calibration status. The region is the supplied mapping/terrain coverage, not a complete archaeological Angkor reconstruction. Neither source completeness nor correspondence to one historical period has been established.

## Stage 1: feature adjacency graph

The full original water inventory supplies 4,891 uniquely identified feature nodes: 67 Canal polygons, 8 Water linear traces, 126 Temple Moats, and 4,690 Ponds. Original FIDs remain in IDs. This is a feature-adjacency (dual) graph: a canal feature is a conveyance feature-node, not already a fully surveyed reach/junction centreline. Feature anchors and connecting lines shown on the map are schematic. Source outlines remain available underneath.

Exact intersection/contact links are labelled `geometric_contact_unverified` and enabled only as the initial geometric-contact scenario. They do not prove historical or hydraulic connectivity. Lines are buffered by an explicit hypothetical 2 m width. Nearby feature pairs within configurable 50 m become `proposed_gap_requires_review`; these are disabled hydraulically by default. The initial graph contains 76 enabled contact links and 13,103 disabled gap proposals. Viewing dashed proposals or changing the display distance does not enable solver connections.

`accepted_gap_links` explicitly enables named proposals on rebuild; `rejected_links` can disable contact or proposed links. Review banks, embankments, gates, culverts, elevations, feature age and modern alterations before accepting. No automatic obstacle-crossing or archaeological chronology inference is implemented. Optional bank/raised-feature layers in the inspector support this review but are not yet automatic structure constraints.

The component-size table at 0/5/15/50 m shows *hypothetical geometric connectivity* if all links within that distance were considered, independent of which review links are enabled. It is sensitivity evidence, not confidence or validation. A large connected component at 50 m does not justify opening all gaps.

## Stage 2: hydraulic cells

Water trace, canal, moat, then pond ownership assigns overlapping water areas once, using stable priority and source-ID ordering. Areas clipped outside the rectangular terrain footprint are logged. Ponds become lumped storage polygons, with disconnected parts kept separate. Canals, moats and buffered water traces are subdivided by a configurable 100 m grid, retaining actual clipped geometry rather than entire wet bounding squares. Subdivision can be refined later; changing it changes numerical resolution and IDs.

Minimum 5 m² slivers and cells without adequate sampled valid terrain are logged, not silently assigned elevations. Terrain validity is estimated from a bounded masked sample (up to 256 x 256 per cell). At least 80% of sampled cell interior must have valid terrain by default. Every retained cell records its sample coverage. This is not a proof of bathymetric completeness.

Retained cells share solver interfaces only where their boundaries overlap along a positive length. Point touches do not conduct water. Cross-feature interfaces must also satisfy the enabled feature-contact scenario. Explicitly accepted gap links use hypothetical width and representative distance. Raw geometric overlaps and cell interfaces therefore remain an archaeological-review issue, not an automatic representation of gates or weirs.

Initial output: 7,645 terrain-supported cells, 3,840 interfaces, 4,827 disconnected components. The largest components contain 623 and 604 cells; most small isolated components represent unconnected storage features. Thousands of numerical sliver exclusions total only about 141 m²; inspect the manifest for exact exclusion counts, reasons, source IDs and areas.

Each cell has mapped plan area, sampled 20th-percentile present terrain minus assumed 0.5 m incision, and a hypothetical initial 0.1 m water depth. These are editable scenario assumptions. Interface width is shared geometry length; solver path length is a centroid-distance proxy, not a surveyed channel centreline length. Ponds currently have constant area vs stage, not surveyed stage-storage curves. Vertical units/datum remain provisional.

## Initial solver result and limits

The existing conservative diffusion-wave storage solver runs a **0.5-second closed-boundary conservation demonstration** across the entire cell system, using hypothetical Manning n=0.05. No observed rainfall, upstream hydrograph, outlet stage, operational controls, calibrated groundwater or reservoir bathymetry is supplied. This short run checks operability and numerical accounting; it is not a hydrological event, historical flow prediction or equilibrium solution.

Regional groundwater is disabled pending regional column areas, aquifer connectivity and head parameterization. The original pilot groundwater controls remain available. Regional biological/chemical transport coupling is not added by this build; the existing interval adapter supports at most 500 cells. A numerical demonstration does not establish regional solute predictions.

## Dashboard

In `/channel-inspector`, Model view selects:
- Regional feature graph: all source anchors, enabled contacts, optional dashed gap proposals, and a display-only distance threshold.
- Regional hydraulic cells: simulated cell depth and interface flow through saved times.
- Original 256 m pilot: existing editable surface/groundwater scenario.

Load / zoom to flow fits the selected model. Network view hides imagery/terrain for a graph view; Layered view restores them. Regional scenario reruns are currently offline through the config/build script; the browser Run button is limited to the pilot so it cannot accidentally apply pilot reconstruction logic to regional geometry. Source and proposed links remain inspectable by tooltip.

## Validation

Synthetic tests cover contact vs gaps, overlap ownership, disconnected geometry parts, point-touch exclusion and logged slivers. Browser verification covers all three views and proposal display without enabling solver links. Artifact verification checks finite positive storage areas, link endpoints, overlap and interval water balance. These are software checks, not archaeological or hydrological validation.
