# QModel — Angkor waterways research

A local research inventory for reconstructing Angkor's water network, identifying the geometry and observations needed for hydraulic simulation, and planning subsequent bacterial transport modelling.

## Run the dashboard

Requires Python 3.9 or newer; no third-party server dependencies. Python 3.12 is available on the current host.

```bash
python3.12 server.py --port 9090
```

Open <http://localhost:9090/>. The server binds to all interfaces by default. For local access only, add `--host 127.0.0.1`. Remote use may require forwarding port 9090.

The dashboard includes searchable resource descriptions, limitations, local downloads, acquisition priorities and a staged research pathway. It serves the collected assets but does not run a hydraulic or bacterial model.

## Project contents

- `server.py`: read-only HTTP server, inventory API and readiness endpoint.
- `web/`: dashboard interface and curated descriptions/acquisition priorities.
- `assets/`: collected manuscripts, supplements, model documentation, Archaeoscape source snapshot and provenance records.
- `angkor_waterways_literature_review.md`: targeted literature review and evidence for existing reconstructions.

See [the collection inventory](assets/README.md) for source links, scope and access gaps. The October 2026 collection contains 13 PDFs, one DOCX supplement and an Archaeoscape source archive. It does not contain the georeferenced GIS/LiDAR datasets or runnable Angkor hydraulic project files. File availability is checked against disk by the API.

Downloaded works retain their original copyright and licence terms. This research collection should be held in a private repository; permission to download an article is not a blanket licence to republish it publicly. Archaeoscape's source licence is retained in `assets/models/archaeoscape/LICENSE`. No restricted archaeological dataset has been acquired or included.

Runtime logs, screenshots, PIDs, SSH-agent sockets and Python caches are ignored. The original input PDFs in `resources/` remain local; their canonical copies are included in `assets/manuscripts/`.

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
