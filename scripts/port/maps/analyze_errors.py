#!/usr/bin/env python3
"""Parse a javac error log into structured records and classify them.

Usage:
  analyze_errors.py <javac-log> [--list-kind KIND] [--limit N]

Classification of "cannot find symbol" records:
  auto-member   - the symbol is a member of a mapped class and the member table
                  gives exactly one candidate -> the rename loop can fix it
  ambiguous     - member table gives several candidates
  unmapped-cls  - the location class is not in the class map at all
  no-member     - class is mapped but the member has no entry
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

ERR_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+): error: (?P<msg>.*)$")
SYM_RE = re.compile(r"^\s*symbol:\s+(?:(?P<kind>\w+)\s+)?(?P<name>\S+?)(?:\(.*\))?\s*$")
LOC_RE = re.compile(r"^\s*location:\s+(?:(?P<kind>\w+)\s+)?(?P<name>\S+?)(?:<.*>)?\s*$")


def load_maps():
    data = json.loads((HERE / "maps.json").read_text(encoding="utf-8"))
    classes = data["classes"]
    members = data["members"]
    rev = {}
    for yarn, moj in classes.items():
        rev.setdefault(moj, yarn)
    return classes, members, rev


def parse_log(path):
    records = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = ERR_RE.match(line)
            if m:
                cur = {
                    "file": m.group("file"),
                    "line": int(m.group("line")),
                    "msg": m.group("msg"),
                }
                records.append(cur)
                continue
            if cur is None:
                continue
            sm = SYM_RE.match(line)
            if sm and "symbol" not in cur:
                cur["sym_kind"] = sm.group("kind") or "class"
                cur["sym_name"] = sm.group("name")
                continue
            lm = LOC_RE.match(line)
            if lm and "loc" not in cur:
                cur["loc_kind"] = lm.group("kind")
                cur["loc_name"] = lm.group("name")
    return records


def classify(records, classes, members, rev):
    out = []
    for r in records:
        if not r["msg"].startswith("cannot find symbol"):
            r["class"] = "other"
            out.append(r)
            continue
        loc = r.get("loc_name")
        name = r.get("sym_name")
        if r.get("loc_kind") not in (None, "class", "interface", "enum", "record"):
            r["class"] = "indirect-location"
            out.append(r)
            continue
        if not loc or not name:
            r["class"] = "no-location"
            out.append(r)
            continue
        yarn_cls = rev.get(loc)
        if yarn_cls is None:
            r["class"] = "unmapped-cls"
            out.append(r)
            continue
        cands = members.get(f"{yarn_cls}#{name}")
        if not cands:
            r["class"] = "no-member"
            out.append(r)
            continue
        r["candidates"] = cands
        r["class"] = "auto-member" if len(cands) == 1 else "ambiguous"
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--list-kind")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    classes, members, rev = load_maps()
    records = parse_log(args.log)
    records = classify(records, classes, members, rev)

    print(f"records parsed: {len(records)}\n")
    print("=== by class ===")
    for k, v in Counter(r["class"] for r in records).most_common():
        print(f"  {v:7d}  {k}")

    print("\n=== top error messages ===")
    norm = Counter()
    for r in records:
        norm[re.sub(r"\d+", "N", r["msg"])] += 1
    for msg, v in norm.most_common(15):
        print(f"  {v:7d}  {msg[:110]}")

    print("\n=== cannot find symbol: top missing symbols (auto-member only) ===")
    syms = Counter(
        (r.get("loc_name"), r.get("sym_name"))
        for r in records
        if r["class"] == "auto-member"
    )
    for (loc, sym), v in syms.most_common(20):
        print(f"  {v:5d}  {loc}#{sym}")

    print("\n=== top unmapped location classes ===")
    um = Counter(r.get("loc_name") for r in records if r["class"] == "unmapped-cls")
    for loc, v in um.most_common(20):
        print(f"  {v:5d}  {loc}")

    print("\n=== top no-member symbols ===")
    nm = Counter(
        (r.get("loc_name"), r.get("sym_name"))
        for r in records
        if r["class"] == "no-member"
    )
    for (loc, sym), v in nm.most_common(20):
        print(f"  {v:5d}  {loc}#{sym}")

    if args.list_kind:
        print(f"\n=== records of class {args.list_kind} ===")
        shown = 0
        for r in records:
            if r["class"] != args.list_kind:
                continue
            print(f"  {r['file'].split('/')[-1]}:{r['line']}  {r['msg']}"
                  f"  [{r.get('sym_kind')} {r.get('sym_name')} @ {r.get('loc_name')}]")
            shown += 1
            if shown >= args.limit:
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
