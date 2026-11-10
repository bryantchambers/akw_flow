# Anonymous Archaeoscape channel extraction

## Acquisition status (2026-11-09)

No Archaeoscape survey rasters have been acquired by this workflow. The public Zenodo record has restricted files:
https://zenodo.org/records/14409524

EFEO requires a standardized access request, explicit licence consent, full name, email, affiliation, position, supervisor/department-head name and email, and institutional support confirmation:
https://archaeoscape.ai/data/2024/request

An approved Zenodo account or guest download link is needed. Do not put access tokens or guest links in tracked files, commands, chat or logs. Download authorized inputs into ignored `private_data/archaeoscape/`; local parcel derivatives go into ignored `private_outputs/archaeoscape/`. Neither directory is served by server.py. Do not locate the parcels or combine them geographically. Each collaborator must obtain their own authorized access.

Request description (append after EFEO's generated standardized message):

> We propose non-commercial archaeological methods research using anonymous parcel-local terrain. We will evaluate parameter-sensitive extraction of candidate channels and local drainage networks, without attempting to identify parcel locations. Could you confirm the nDTM normalization transform, elevation units/encoding, DTM band layout, and whether relative slopes and cross-section heights are preserved? Please also advise conditions for sharing derived graphs or figures. We can start with one small parcel or window rather than downloading the full archive.

## Implementation ready for authorized inputs

```bash
/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python scripts/extract_archaeoscape_network.py --input private_data/archaeoscape/PARCEL.tif --inspect
```

Copy `configs/archaeoscape_extraction.json` to a local private config. Set the documented DTM band, pixel size, and elevation conversion to metres. Verify the nDTM transform preserves metric relative elevations and only then set `relative_elevations_verified` true. A simple elevation offset does not change slopes. Spatial detrending requires further methodological work; do not label its gradients observed hydraulic slopes.

```bash
/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel/bin/python scripts/extract_archaeoscape_network.py --input private_data/archaeoscape/PARCEL.tif --config private_data/archaeoscape/extraction.json
```

Start with 512 x 512 pixels (256 m square at 0.5 m). The whole 888 km² archive is not necessary for the pilot. Inputs are read as windows. Exported coordinates are an arbitrary window-local Cartesian system; never import these as WGS84 into the existing geographic viewer.

## Sensitivity and interpretation

Profiles vary minimum contributing area and local depression. Lower thresholds retain weaker, smaller terrain candidates. The following can also be varied in independent runs: smoothing sigma, local-relief radius, downhill slope floor, component length and excluded cells. Sigma is a Gaussian standard deviation, not channel width. Smoothing suppresses noise but may erase faint banks; start at zero. The sensitive profile is not evidence of older age.

The method uses strict-downhill D8 contributing area and local mean elevation minus cell elevation. Missing data and manually excluded cells are barriers; diagonal corner crossing is prohibited. Local relief is only evaluated where the full neighbourhood is supported. Pit filling, breaching and artificial inter-parcel joins are deliberately absent. Sinks and flats terminate routes. Edge/hole truncation makes accumulation incomplete. Candidate graph directions describe terrain descent; backwater or reverse hydraulic flow requires a separate solver.

`sensitivity.json` records edge membership across profiles, not statistical confidence. Width and bed depth remain null: this graph is NOT silently passed to the hydraulic solver with fabricated channel geometry. Cross-sections, structures, ponds/reservoir storage, boundary forcing and archaeological interpretation must be reviewed before flow simulation. Annotations and RGB are not automatically assimilated yet; hydrology labels combine multiple water-feature types and require a documented class mapping. No Archaeoscape-specific extraction or hydraulic result is claimed until real authorized rasters are processed.

Synthetic tests cover a descending valley, threshold nesting, metric link lengths, constant vertical offsets, flats and missing-data barriers. These validate algorithmic properties, not performance on EFEO data.
