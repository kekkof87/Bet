#!/usr/bin/env python
from core.persistence import load_latest_fixtures
import json
import sys

def main():
    fixtures = load_latest_fixtures()
    print(f"Fixtures memorizzate: {len(fixtures)}")
    if fixtures:
        first = fixtures[0]
        print("Prima fixture:")
        print(json.dumps(first, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
