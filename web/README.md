# Local Angkor research dashboard

Start from any directory:

```bash
python3.11 /maps/projects/caeg/people/gfx654/Projects/AKW/QModel/server.py --port 9090
```

Open `http://localhost:9090`. The server binds to all interfaces by default; use `--host 127.0.0.1` for loopback only. It serves the dashboard and this project's `assets/` collection, not the rest of the workspace.

Descriptions and acquisition priorities are in `web/catalog.json`. File availability, sizes, source links and PDF page counts are read from the collection manifests each time `/api/catalog` is requested. Update the manifests and curated descriptions when new data arrive. Geospatial dataset and hydraulic project counts currently represent the audited collection (both zero); update the server's classification when these are acquired.

Routes: `/` (dashboard), `/api/catalog` (inventory JSON), `/healthz` (readiness), and `/assets/...` (collected files). Downloaded HTML is delivered as an attachment. No external dependencies or external fonts are needed.

For the server launched by Codex, the PID and output are in `.runtime/server-9090.pid` and `.runtime/server-9090.log`. Confirm the PID still refers to this server before stopping it. A remote workspace may require forwarding TCP port 9090 to access it from your own browser.

## Model view (6 November 2026)

`/model-view` serves a local Three.js viewer with actual Copernicus context terrain, modern OSM waterways, a provisional fence, optional drainage-screening colours, location inspection, orbit/zoom/pan, top view, height exaggeration and browser-local GeoJSON model-output import. `web/vendor/` contains Three.js 0.170.0 and OrbitControls under the retained MIT licence. No CDN is needed at runtime.

See `assets/data/context/README.md` for source resolution, the deliberately limited D8 screening method, provenance and rebuild commands. The new context datasets are listed separately from the still-missing archaeological GIS/LiDAR. No calibrated hydraulic or bacterial output is bundled.

## Selectable TOPSAR previews — 6 November 2026

The terrain selector now offers Copernicus, a native-spacing ~5 m TOPSAR detail around Angkor Wat, and a full-strip ~80 m display overview. Direct links: `/model-view?terrain=topsar_detail` and `/model-view?terrain=topsar_overview`. These are separate datasets, not a fused elevation surface. TOPSAR heights are WGS84 ellipsoidal; its fill mask and ground accuracy remain provisional. Drainage screening is unavailable for TOPSAR, while properly declared user model output can still be imported over valid coverage.

See `assets/data/context/topsar/CONVERSION.md` and `conversion_provenance.json` for the SCH conversion and checks. `scripts/build_topsar_scenes.py` regenerates the scenes from the unchanged source, with pyproj added to the GIS preparation environment. Source/display resolution labels and pixel-centre positioning are explicit.
