# Connection review and terrain geometry workspace

## What is implemented

Open `/channel-inspector` and choose **Review workspace**. A bounded breadth-first candidate workspace starts at `angkor_center_features:ANG_F_09042`, considers links within 15 m, and includes up to 25 source features. The current workspace has 24 queued links. This is a potential subnetwork for review, not an accepted connected historical system.

Select links from the queue or click a regional feature-graph edge. The selected connection highlights red. Record **accepted**, **rejected**, or **unresolved**, plus reviewer, evidence, period/scenario and rationale. Accepted means accepted as a *scenario hypothesis*, not independently validated archaeology. Acceptance requires evidence text and rationale. **Screen terrain and mapped barriers** checks valid terrain samples along the candidate segment and intersections with source Pond Bank/Raised Linear polygons. An intersection is a review flag, not proof of a barrier, gate or culvert. A missing intersection is not proof of an opening. Geometric contacts remain ambiguous.

The ledger is `assets/private/channel_review/reviews.json`; original data are never edited. Saves are atomic and revision-checked, with before/after history, UTC times and current graph SHA256. Conflicting/stale browser edits and graph changes are rejected. The service has no researcher authentication: the reviewer name is self-reported, and people who can reach port9090 can access the selected research derivatives. Cross-origin browser writes are blocked. Do not expose the service publicly without appropriate access controls.

**Saving does not alter existing solver output.** The workspace shows saved vs applied review revision. **Rebuild regional model from saved reviews** applies a snapshot using the existing regional config. Accepted links enable scenario connections; rejected AND explicitly unresolved links disable them, including default geometric contacts. Unreviewed geometric contacts retain the baseline unverified-contact behavior. Saved decisions take precedence over accepted/rejected lists in the configuration. Unknown source IDs fail rebuilding instead of disappearing. Rebuilding is serialized with other flow runs.

Period/scenario text records provenance; it is not an automatic chronology filter. This ledger represents one working scenario. Do not interpret a mixture of incompatible periods as a validated reconstruction. Multiple named historical configurations remain future work.

## Geometry and profiles

Choose a feature or click mapped geometry. **Generate provisional guide and profiles** constructs a straight guide along the minimum rotated rectangle's major axis and clips to the longest contiguous mapped segment. For source Water lines it uses the longest line part. These are proxies, not extracted thalwegs or complete curved channel centre-lines. For curved/branched channels, **Draw a guide on map**, click at least two vertices and finish. Drawn guides can be saved with reach assumptions; source line guides are regenerated from immutable source geometry.

Sampling uses original raster values, normally at 0.5 m requested spacing, capped at 4,096 longitudinal samples. NoData and outside-coverage samples remain gaps, not interpolated bridges. A least-squares terrain trend is reported along the guide with valid-data fraction. Direction is arbitrary; no downstream direction is inferred. Three transects at 25/50/75% of guide length are normal to the local guide tangent, with adjustable half-width (5..500 m). Stations run left-to-right relative to guide direction; this is not necessarily downstream orientation. Polygon intersections indicate *mapped water extent*, not surveyed hydraulic bank stations. Real sections may need bent overbank segments and manually reviewed bank locations.

Solid curves are current terrain. Dashed curves illustrate terrain minus a scenario incision inside the mapped water geometry, leaving outside terrain unchanged. A blank incision field displays the regional default, not an observation. The plot is an illustrative geometry scenario, not an exact rendering of each lumped hydraulic cell's percentile bed proxy.

Save per-feature incision, Manning n, uncertainty ranges, evidence, period and rationale. A saved guide and its method are retained. Incision applies to all retained hydraulic cells from that source feature, which may extend beyond the displayed guide. Rebuilding uses per-feature incision instead of the uniform default. Interface roughness uses reviewed values, with scenario defaults for an unreviewed side, and the larger adjacent value at a mixed interface. Ranges are retained for later ensembles, not automatically sampled. Widths are inspected via transects and mapped extents; bankfull width/depth and stage-storage curves are not automatically calibrated from them.

Horizontal CRS is confirmed as EPSG:32648. The TIFF does not establish vertical datum, elevation units, acquisition date, processing or vertical accuracy. Metres remain an explicit provisional assumption. The compound vertical CRS on the vector trace file does not establish the DTM's vertical datum. Survey documentation or custodian confirmation is still required. A 0.5 m pixel size is not a 0.5 m vertical accuracy claim.

## Prepared evidence (private)

`assets/private/channel_review/prepared_evidence.json` contains three initial longitudinal profiles, nine transects and screens for all 24 candidate links. Five links intersect mapped bank/raised-feature geometry; all 24 candidate segments had valid sampled terrain. Nothing has been automatically accepted or rejected, and no unsupported numerical uncertainty or historical date has been assigned.

## Literature checked and library entries

- USACE HEC-RAS Mapper, **Cross Sections**: https://www.hec.usace.army.mil/confluence/rasdocs/rmum/latest/geometry-data/cross-sections
- USGS Lidar Base Specification, **Hydro-Flattening Reference**: https://www.usgs.gov/ngp-standards-and-specifications/lidar-base-specification-appendix-2-hydro-flattening-reference

Both are in the dashboard resource library with archived official HTML and source links. HEC guidance informs perpendicular placement and manual bank/geometry review. USGS distinguishes topographic hydro-flattening from hydrologic conditioning and notes terrain/structure issues. Neither establishes how the Huma-Num DTM was processed, nor validates Angkor geometry or archaeology.

## Verification and next acceptance

Tests cover revision conflicts, graph mismatches, audit persistence, acceptance evidence requirements, valid parameter ranges, HTTP validation/origin checks, terrain sampling/NoData, transect orientation, unchanged source raster bytes and model application of decisions/parameters. Browser QA covers profiles, scenario overlays, queued links and responsive layout. Manual acceptance requires reviewing links against terrain, imagery, banks/structures and archaeological phase evidence; numerical tests cannot replace that review.
