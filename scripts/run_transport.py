#!/usr/bin/env python3
"""Run a transport configuration; write complete result and optional viewer GeoJSON."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transport.core import simulate

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('config', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--geojson', type=Path)
    args = p.parse_args()
    result = simulate(json.loads(args.config.read_text()))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    if args.geojson:
        args.geojson.write_text(json.dumps(result['geojson'], indent=2, allow_nan=False) + '\n')
