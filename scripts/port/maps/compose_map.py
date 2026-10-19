#!/usr/bin/env python3
"""Compose maps.json (yarn -> mojmap) with vermap.json (mojmap -> mojmap 26.2).

The member-rename loop reads compiler errors, which speak in FINAL 26.2 names,
while the member table is keyed by yarn names of the source version. Composing
the two tables once gives a single lookup: yarn name -> final 26.2 name, plus
the reverse index the fixer needs to go from a reported class back to yarn.

Usage: compose_map.py --maps <maps.json> --vermap <vermap.json> --out <out.json>
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", required=True)
    ap.add_argument("--vermap", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    maps = json.loads(Path(args.maps).read_text(encoding="utf-8"))
    vermap = json.loads(Path(args.vermap).read_text(encoding="utf-8"))
    v_classes = vermap["classes"]
    v_members = vermap["members"]

    classes = {}
    for yarn, moj in maps["classes"].items():
        classes[yarn] = v_classes.get(moj, moj)

    members = defaultdict(list)
    for key, cands in maps["members"].items():
        yarn_cls, _, member = key.partition("#")
        old_moj = maps["classes"].get(yarn_cls)
        for cand in cands:
            finals = [cand]
            if old_moj is not None:
                finals = v_members.get(f"{old_moj}#{cand}", [cand])
            for final in finals:
                if final not in members[key]:
                    members[key].append(final)

    out = {
        "classes": classes,
        "members": dict(members),
        "stats": {
            "maps": args.maps,
            "vermap": args.vermap,
            "classes": len(classes),
            "member_keys": len(members),
        },
    }
    dest = Path(args.out)
    dest.write_text(json.dumps(out), encoding="utf-8")
    print(f"classes    : {len(classes)}")
    print(f"member keys: {len(members)}")
    print(f"written    : {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
