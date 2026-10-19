#!/usr/bin/env python3
"""Resolve `cannot find symbol` errors into member renames, using maps.json.

The class rename already happened; what is left are method and field names that
only the compiler can point at. javac tells us the exact file, line and caret
column of the failing identifier, so the rename is applied to that one token.

Owner resolution: javac prints a simple name (`location: class LocalPlayer` or
`location: variable player of type LocalPlayer`). Simple names are resolved
through the class map; when a simple name is ambiguous the record is skipped
rather than guessed at.

Usage:
  fix_members.py <javac-log> [--apply] [--limit N] [--report-unknown]
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from javac_log import parse_log  # noqa: E402

IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def load_maps(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    classes = data["classes"]
    members = data["members"]
    rev = {}
    for yarn, moj in classes.items():
        rev.setdefault(moj, yarn)
    simple = defaultdict(set)
    for moj in classes.values():
        simple[moj.rsplit(".", 1)[-1]].add(moj)
    # Fallback index: javac reports the *static* type of the receiver, but the
    # member may be declared in an ancestor (LocalPlayer#getPos lives on Entity).
    # When the per-class lookup misses, a member name that maps to exactly one
    # mojmap name everywhere is still safe to apply.
    global_index = defaultdict(Counter)
    for key, cands in members.items():
        member = key.split("#", 1)[1]
        for c in cands:
            global_index[member][c] += 1
    return classes, members, rev, simple, global_index


def load_hierarchy(path):
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def lookup_member(members, global_index, hierarchy, yarn_owner, name):
    """-> (candidate, source) or (None, reason).

    Resolution order: the class itself, then its ancestors (javac reports the
    static type of the receiver, the member may be declared further up), then a
    global name index when that name is unambiguous everywhere.
    """
    cands = members.get(f"{yarn_owner}#{name}")
    if cands:
        if len(cands) == 1:
            return cands[0], "class"
        return None, "member-ambiguous"

    seen = {yarn_owner}
    queue = list(hierarchy.get(yarn_owner, []))
    while queue:
        cls = queue.pop(0)
        if cls in seen:
            continue
        seen.add(cls)
        cands = members.get(f"{cls}#{name}")
        if cands:
            if len(cands) == 1:
                return cands[0], "inherited"
            return None, "member-ambiguous"
        queue.extend(hierarchy.get(cls, []))

    g = global_index.get(name)
    if not g:
        return None, "no-member-entry"
    if len(g) == 1:
        return next(iter(g)), "global"
    return None, "global-ambiguous"


IMPORT_RE = re.compile(r"^\s*import\s+(?!static)([A-Za-z0-9_$.]+)\s*;\s*$", re.M)


def file_imports(path_str, cache):
    """simple name -> mojmap fqn, from the file's own import block."""
    if path_str in cache:
        return cache[path_str]
    out = {}
    try:
        text = Path(path_str).read_text(encoding="utf-8", errors="replace")
    except OSError:
        cache[path_str] = out
        return out
    for m in IMPORT_RE.finditer(text):
        fqn = m.group(1)
        out[fqn.rsplit(".", 1)[-1]] = fqn
    cache[path_str] = out
    return out


def plan(records, members, rev, simple, global_index, hierarchy, only=None):
    fixes = defaultdict(list)   # file -> [(line, col, old, new)]
    stats = Counter()
    unknown = Counter()
    imp_cache = {}

    for r in records:
        if only and only not in r.file:
            continue
        if not r.msg.startswith("cannot find symbol"):
            continue
        if r.sym_kind not in ("method", "variable"):
            stats["skip:not-a-member"] += 1
            continue
        if not r.loc_name or not r.sym_name:
            stats["skip:no-location"] += 1
            continue
        # the file's own imports are the strongest signal for a simple name
        imported = file_imports(r.file, imp_cache).get(r.loc_name)
        if imported is not None:
            moj_owner = imported
            stats["owner:from-import"] += 1
        else:
            owners = simple.get(r.loc_name)
            if not owners:
                stats["skip:owner-not-in-map"] += 1
                unknown[f"{r.loc_name}#{r.sym_name}"] += 1
                continue
            if len(owners) > 1:
                stats["skip:owner-ambiguous"] += 1
                unknown[f"{r.loc_name}#{r.sym_name}"] += 1
                continue
            moj_owner = next(iter(owners))
            stats["owner:from-global-index"] += 1
        yarn_owner = rev.get(moj_owner)
        if yarn_owner is None:
            stats["skip:owner-unmapped"] += 1
            continue
        new, source = lookup_member(members, global_index, hierarchy,
                                    yarn_owner, r.sym_name)
        if new is None:
            stats[f"skip:{source}"] += 1
            unknown[f"{r.loc_name}#{r.sym_name}"] += 1
            continue
        if r.col is None:
            stats["skip:no-caret"] += 1
            continue
        fixes[r.file].append((r.line, r.col, r.sym_name, new))
        stats[f"planned:{source}"] += 1

    return fixes, stats, unknown


def resolve_position(src, col, old):
    """Find the offset of `old` on this line, preferring javac's caret column."""
    if src[col:col + len(old)] == old:
        return col
    m = IDENT_RE.match(src, col)
    if m and m.group(0) == old:
        return col
    found = [mm.start() for mm in re.finditer(
        rf"(?<![\w$]){re.escape(old)}(?![\w$])", src)]
    if not found:
        return None
    return min(found, key=lambda p: abs(p - col))


def apply_fixes(fixes, limit=None):
    """Apply planned renames bottom-up.

    javac reports the same failing token once per error record, so the same
    identifier can arrive with several caret columns. Renames are therefore
    keyed by resolved token position: duplicates collapse, and a line is
    rewritten right-to-left so earlier offsets stay valid.
    """
    applied = 0
    failed = 0
    touched = 0
    for path_str, items in fixes.items():
        path = Path(path_str)
        if not path.exists():
            failed += len(items)
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        per_line = defaultdict(dict)   # line_no -> {pos: (old, new)}
        for line_no, col, old, new in items:
            idx = line_no - 1
            if idx < 0 or idx >= len(lines):
                failed += 1
                continue
            pos = resolve_position(lines[idx], col, old)
            if pos is None:
                failed += 1
                continue
            per_line[line_no][pos] = (old, new)

        changed = False
        for line_no, positions in per_line.items():
            idx = line_no - 1
            src = lines[idx]
            for pos in sorted(positions, reverse=True):
                old, new = positions[pos]
                if src[pos:pos + len(old)] != old:
                    failed += 1
                    continue
                src = src[:pos] + new + src[pos + len(old):]
                applied += 1
                changed = True
            lines[idx] = src
        if changed:
            path.write_text("\n".join(lines), encoding="utf-8")
            touched += 1
    return applied, failed, touched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--map", required=True, help="maps.json for the source version")
    ap.add_argument("--hierarchy", required=True, help="hierarchy.json for the source version")
    ap.add_argument("--only", help="restrict to records whose path contains this")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--report-unknown", type=int, default=20)
    args = ap.parse_args()

    _classes, members, rev, simple, global_index = load_maps(args.map)
    hierarchy = load_hierarchy(args.hierarchy)
    records = parse_log(args.log)
    print(f"records parsed: {len(records)}")
    print(f"hierarchy     : {len(hierarchy)} classes")

    fixes, stats, unknown = plan(records, members, rev, simple, global_index,
                                 hierarchy, args.only)
    print("\n=== plan ===")
    for k, v in stats.most_common():
        print(f"  {v:7d}  {k}")
    print(f"  {sum(len(v) for v in fixes.values()):7d}  fixes over "
          f"{len(fixes)} files")

    if args.report_unknown:
        print("\n=== top unresolved (owner#member) ===")
        for k, v in unknown.most_common(args.report_unknown):
            print(f"  {v:5d}  {k}")

    if args.apply:
        applied, failed, touched = apply_fixes(fixes, args.limit)
        print(f"\napplied: {applied}  failed: {failed}  files touched: {touched}")
    else:
        print("\n(dry run; pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
