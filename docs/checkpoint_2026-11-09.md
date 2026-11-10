# Checkpoint — connection review and geometry, 9 November 2026

## Open tomorrow

Dashboard: http://dandycomp06fl.unicph.domain:9090/channel-inspector

Choose **Review workspace** in the map toolbar. The initial focus is a 25-feature candidate workspace around `angkor_center_features:ANG_F_09042`, with 24 queued links (7 geometric contacts, 17 positive gaps). This is a review target, not an accepted connected historical subnetwork.

1. Select a connection from the queue, or click a regional feature-graph link.
2. Use **Screen terrain and mapped barriers**, then inspect imagery, mapped banks/raised features and terrain. Five of the 24 segments intersect mapped bank/raised geometry. This flags ambiguity; it does not establish a gate, obstruction or working connection.
3. Record accepted/rejected/unresolved, evidence, rationale and a period/scenario description. No connection has been accepted or rejected automatically. The production review ledger remains revision 0.
4. Select a source feature and generate terrain profiles. Replace the default straight guide with a drawn guide for a curved channel. Inspect the longitudinal profile, three perpendicular transects and mapped feature spans.
5. Save reach-specific incision/roughness and uncertainty ranges, if justified. These are scenario assumptions, not bathymetric measurements. Blank values inherit the regional defaults.
6. **Rebuild regional model from saved reviews** applies the recorded decisions/point parameters. Check saved vs model revision. Ranges are recorded for later ensembles; they are not automatically simulated.

## Completed software and prepared evidence

- Persistent, atomic review ledger with original source IDs, evidence/notes, UTC timestamps, graph hash, revision checks and before/after history.
- Acceptance requires explicit evidence and rationale. Unresolved/rejected saved reviews disable a link on rebuild; saved decisions override config lists. Unreviewed geometric contacts retain the original unverified baseline.
- Reach assumptions feed into regional cell-bed incision and interface Manning overrides. Drawn/provisional guides can be saved with method provenance.
- Raw terrain is read-only; scenario incision is drawn separately inside mapped water geometry. NoData remains gaps. Guide direction is arbitrary, not established downstream.
- Source bank/raised-feature intersection and terrain screening are available on demand.
- Private `assets/private/channel_review/prepared_evidence.json` contains 3 initial feature profiles and 9 transects, plus all 24 connection screens. All candidate segments had valid sampled terrain; 5 had mapped barrier intersections. Initial automatic-guide lengths are approximately 449.1, 190.7 and 192.0 m.
- USACE HEC-RAS cross-section guidance and USGS hydro-flattening reference are in the resource library with local official HTML, source links and checksums.
- Safe managed-server restart helper waits for the old process to exit, then verifies the listener; it avoids the restart/port-release race found in QA.

## Verification

- 68 unit/regression tests passed, including audit persistence, conflicts/stale graph detection, acceptance evidence, HTTP/origin validation, terrain NoData sampling, perpendicular transects, unchanged source raster bytes and application of review decisions/parameters.
- Browser checks exercised queued links, missing-evidence rejection without creating production reviews, barrier screening, four profile plots, incision overlay, an actual map-click drawn guide, and mobile layout without horizontal overflow or JavaScript errors.
- Full regional rebuild through the actual review API preserved 7,645 cells / 3,840 interfaces at applied review revision 0, with zero reported global water-budget residual in the unchanged short closed scenario.
- Source literature archive content was checked against the methodological text. The asset checksum manifest was updated for new references and acquisition metadata.
- QA reports/screenshots are under ignored `.runtime/`, including `channel-review-final-verification.json`, `review-rebuild-verification.json` and `channel-review-final-desktop.png`.

## Scientific limits and next acceptance gate

Horizontal CRS is EPSG:32648. The supplied TIFF does not establish vertical datum, elevation units, acquisition date, processing details or vertical accuracy. Metres remain provisional. The trace file's vertical CRS does not prove the DTM's datum. Source documentation/custodian confirmation is still needed; 0.5 m sampling does not establish vertical accuracy.

Automatic straight guides are geometry proxies, not curved thalwegs. Two-point perpendicular transects are preliminary; surveyed bank stations, bent overbank sections, channel beds and structures need review. A topographic DEM may preserve a crossing road or depict a water surface; no assumption that this source is hydro-conditioned is justified.

The interface records one working scenario. Period text is descriptive, not an automatic temporal filter; do not mix incompatible historical phases and call the result validated. Present-day terrain, mapped features and hypothetical historical changes remain separate.

The next acceptance gate is a documented set of connection decisions and reviewed geometry for this focus area, then a deliberately forced hydraulic scenario with timestep/grid sensitivity checks. The regional model still uses a 0.5-second closed conservation demonstration, not a flood or historical prediction. Regional groundwater/solute coupling is not added by these tasks.

## Files and commands

- Workflow and references: `docs/connection_review_and_profiles.md`.
- Review/profile service: `hydraulics/channel_review.py`.
- Browser interface: `web/channel-review.js`, linked from the existing inspector.
- Review ledger (created on first save): `assets/private/channel_review/reviews.json`.
- Restart: `/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python scripts/restart_dashboard.py`.
- Tests: `/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python -m unittest discover -s tests`.
- Regional rebuild: `/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python scripts/build_regional_network.py` or the review button.

All source/private spatial data and review records remain excluded from Git. These implementation changes have not been committed or pushed. The dashboard remains running on port 9090. It has no researcher authentication; do not expose write endpoints beyond the authorized research audience. No external messages or access requests were sent.
