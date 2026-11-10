# QModel — Angkor waterways research

A local research dashboard and exploratory modelling workspace for reconstructing Angkor's water network, identifying the geometry and observations needed for hydraulic simulation, and planning subsequent bacterial transport modelling.

## Run the dashboard

Use Python 3.12 with `scripts/requirements-gis.txt` installed for channel review, terrain profiles and simulation endpoints. The base inventory server itself uses the standard library.

```bash
mamba activate qmodel
python server.py --port 9090
```

Open <http://localhost:9090/>. The server binds to all interfaces by default. For local access only, add `--host 127.0.0.1`. Remote use may require forwarding port 9090.

The dashboard includes the resource library, channel inspector, regional feature/cell networks, persistent connection review, terrain profiles and exploratory hydraulic/transport models. These are uncalibrated research scenarios; model assumptions and data gaps are explicit. Open `/channel-inspector` and choose **Review workspace** to continue the current work.

## Fixed-terrain flow MVP — 10 November 2026

The channel inspector now includes **New · fixed-terrain 2D pilot**: a 640 m square, 10 m computational grid using 0.5 m terrain storage and face profiles. It supports changing wetted connections, wetting/drying, reversal, fixed scenario geometry, explicit stage forcing and conservative unit-tracer routing. Select it and click **Load / zoom to flow**. The existing regional adjacency models are retained.

Build with `python3.12 scripts/build_terrain_flow.py`; edit `configs/terrain_flow.json`, or edit and run in the inspector. See [method, controls and validation limits](docs/fixed_terrain_flow.md). This is a new local pilot, not a validated regional hydraulic network or bacterial hotspot prediction. Regional watershed extraction, bank-aligned refinement and transport reaction/dispersion coupling remain acceptance gates.

The **Bank and mesh review** panel now compares matched 10 m and 5 m runs, highlights native-terrain split pools, plots cell profiles and shows canal-transect flows. See [results and inspection steps](docs/terrain_refinement_review.md). Build with `python3.12 scripts/build_terrain_refinement.py`; the original pilot is preserved.

## Regional native-resolution model

Open `/regional-terrain` for the full supplied survey at **actual 0.5 m hydraulic spacing**: approximately 372 million supported cells over 93 km². The compiled continuous raster solver replaces JSON geometry at this scale; the viewer streams native raster tiles and reads individual cells. See [coverage, operation and validation limits](docs/regional_native_flow.md).

Build using `python3.12 scripts/build_regional_native.py` after installing `scripts/requirements-native.txt` alongside GIS dependencies. The default is a hypothetical 30-second low-water/rainfall startup check, not a regional flood/drought forecast. Private outputs remain local.

## Project contents

- `server.py`: inventory, private inspection derivatives, local review persistence, simulation APIs and readiness endpoint.
- `web/`: dashboard interface and curated descriptions/acquisition priorities.
- `assets/`: collected manuscripts, supplements, model documentation, Archaeoscape source snapshot and provenance records.
- `angkor_waterways_literature_review.md`: targeted literature review and evidence for existing reconstructions.

See [the collection inventory](assets/README.md) for source links, scope and access gaps. The October 2026 collection contains 13 PDFs, one DOCX supplement and an Archaeoscape source archive. That historical inventory predates the November private Huma-Num terrain and derived networks; native external Angkor hydraulic project files remain unavailable. File availability is checked against disk by the API.

Downloaded works retain their original copyright and licence terms. This research collection should be held in a private repository; permission to download an article is not a blanket licence to republish it publicly. Archaeoscape's source licence is retained in `assets/models/archaeoscape/LICENSE`. Restricted survey inputs and spatial derivatives are kept locally under ignored `assets/private/`, with original files blocked from general asset serving. Only explicitly selected inspector/review derivatives are exposed by the research dashboard; none are included in Git.

Runtime logs, screenshots, PIDs, SSH-agent sockets and Python caches are ignored. The original input PDFs in `resources/` remain local; their canonical copies are included in `assets/manuscripts/`.

## Durable environment

Use `mamba activate qmodel`, installed under your Miniforge `envs/qmodel` directory. Recreate it from this repository root with `mamba env create -f environment.yml`. The pinned Python package list is in `scripts/requirements-qmodel.lock.txt`. See [environment operation and temporary-file recovery](docs/environment.md). Regional launches support up to 40 CPU threads.

## Verification

```bash
python3.12 -m py_compile server.py
curl --fail http://localhost:9090/healthz
curl --fail http://localhost:9090/api/catalog
cd assets
sha256sum -c SHA256SUMS
```

Checksums verify the collected files; they do not establish archaeological or hydraulic accuracy. Source code in the research archive has not been installed or executed.

## Geospatial context and 3D view — 6 November 2026

A modern starter package now adds two Copernicus GLO-30 elevation tiles and 1,524 OSM water features. These are georeferenced context, not the missing high-resolution archaeological LiDAR/GIS. Open `/model-view` from the dashboard for 3D terrain, waterways, a provisional study fence, exploratory drainage screening and browser-local model-output import. See [context provenance and limitations](assets/data/context/README.md).

The terrain selector also provides a separate ~5 m TOPSAR detail tile around Angkor Wat and a lighter survey-strip overview. See [TOPSAR conversion and limitations](assets/data/context/topsar/CONVERSION.md); the native post spacing is not a claim of independently validated accuracy, and no TOPSAR flow/hotspot simulation is inferred.

## Connection review and geometry — 9 November 2026

See [the review workflow](docs/connection_review_and_profiles.md) and [the dated checkpoint](docs/checkpoint_2026-11-09.md). Use the GIS environment to run tests: `python -m unittest discover -s tests`. Review decisions and geometry assumptions persist privately with an audit trail; source observations, scenario assumptions and unverified history remain separate.
