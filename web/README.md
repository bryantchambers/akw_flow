# Local Angkor research dashboard

Start from any directory:

```bash
python3.11 /maps/projects/caeg/people/gfx654/Projects/AKW/QModel/server.py --port 9090
```

Open `http://localhost:9090`. The server binds to all interfaces by default; use `--host 127.0.0.1` for loopback only. It serves the dashboard and this project's `assets/` collection, not the rest of the workspace.

Descriptions and acquisition priorities are in `web/catalog.json`. File availability, sizes, source links and PDF page counts are read from the collection manifests each time `/api/catalog` is requested. Update the manifests and curated descriptions when new data arrive. Geospatial dataset and hydraulic project counts currently represent the audited collection (both zero); update the server's classification when these are acquired.

Routes: `/` (dashboard), `/api/catalog` (inventory JSON), `/healthz` (readiness), and `/assets/...` (collected files). Downloaded HTML is delivered as an attachment. No external dependencies or external fonts are needed.

For the server launched by Codex, the PID and output are in `.runtime/server-9090.pid` and `.runtime/server-9090.log`. Confirm the PID still refers to this server before stopping it. A remote workspace may require forwarding TCP port 9090 to access it from your own browser.
