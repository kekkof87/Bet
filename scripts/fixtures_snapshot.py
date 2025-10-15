#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    ap = argparse.ArgumentParser(description="Materialize fixtures.json snapshot from last_delta.json (added)")
    ap.add_argument("--delta-file", default="data/last_delta.json", type=str)
    ap.add_argument("--out", default="data/fixtures.json", type=str)
    args = ap.parse_args()

    dpath = Path(args.delta_file)
    if not dpath.exists():
        print(f"[fixtures_snapshot] {dpath} not found, exiting")
        return
    data = load_json(dpath)
    items: List[Dict] = data.get("added", [])
    out = {"generated_from": dpath.name, "count": len(items), "items": items}
    save_json(Path(args.out), out)
    print(f"[fixtures_snapshot] fixtures snapshot written: {args.out} (items={len(items)})")

if __name__ == "__main__":
    main()
