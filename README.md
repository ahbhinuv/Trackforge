# Rail Drishti — Genuine Multi-Page Full-Stack Prototype

This version has:
- Separate HTML pages
- Proper Flask routes
- Working Leaflet maps on Track Train and Live Network
- OpenStreetMap tiles
- Backend APIs

Pages:
- `/` Home
- `/track` Track Train
- `/network` Live Network
- `/station` Find Station
- `/guide` Rail Drishti Guide
- `/about` About

## Run

```bash
cd rail_drishti_multipage_genuine_mapfixed
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5001

The map requires an internet connection because Leaflet and OpenStreetMap tiles are loaded from their public CDN/services.
