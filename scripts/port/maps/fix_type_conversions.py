#!/usr/bin/env python3
"""Fix `incompatible types` errors where a Direction is passed as a Vec3i/Vec3.

In 26.2 `Direction` no longer implements `Vec3i`, so every `pos.offset(dir)`,
`Vec3.ofCenter(cell.offset(dir))` and similar call site breaks. The replacement
is explicit: `dir.getUnitVec3i()` for Vec3i, `dir.getUnitVec3()` for Vec3.

javac points its caret at the start of the offending expression, so the fix is
to scan that one expression and wrap it. Only simple chains are touched
(identifiers, dots, calls, indexing): anything else is reported and left alone
rather than guessed at.

Usage: fix_type_conversions.py <javac-log> [--apply] [--report N]
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from javac_log import parse_log  # noqa: E402

IDENT_START = re.compile(r"[A-Za-z_$]")
IDENT_CHAR = re.compile(r"[A-Za-z0-9_$]")

# message fragment -> method to append
RULES = {
    "Direction cannot be converted to Vec3i": "getUnitVec3i",
    "Direction cannot be converted to Vec3": "getUnitVec3",
}


def scan_expression(src, start):
    """Return the end offset of a simple expression starting at `start`, or None.

    Accepts identifier chains with calls and indexing: `dir`, `bhr.getDirection()`,
    `a.b(c).d[0]`. Refuses anything with operators, so ternaries and arithmetic
    are left for a human.
    """
    i = start
    n = len(src)
    if i >= n or not IDENT_START.match(src[i]):
        return None
    depth = 0
    while i < n:
        ch = src[i]
        if IDENT_CHAR.match(ch) or ch == ".":
            i += 1
            continue
        if ch == "(" or ch == "[":
            depth += 1
            i += 1
            continue
        if ch == ")" or ch == "]":
            if depth == 0:
                break
            depth -= 1
            i += 1
            continue
        break
    if depth != 0:
        return None
    expr = src[start:i]
    if not expr or expr.endswith("."):
        return None
    return i


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", type=int, default=15)
    args = ap.parse_args()

    records = parse_log(args.log)
    plan = defaultdict(list)
    stats = Counter()
    skipped = Counter()

    for r in records:
        method = None
        for frag, meth in RULES.items():
            if frag in r.msg:
                method = meth
                break
        if method is None:
            continue
        if r.col is None or r.source_line is None:
            stats["skip:no-caret"] += 1
            continue
        src = r.source_line
        end = scan_expression(src, r.col)
        if end is None:
            stats["skip:complex-expression"] += 1
            skipped[src.strip()[:70]] += 1
            continue
        expr = src[r.col:end]
        if f".{method}()" in expr:
            stats["skip:already-fixed"] += 1
            continue
        plan[r.file].append((r.line, r.col, end, expr, method))
        stats["planned"] += 1

    print(f"records: {len(records)}")
    for k, v in stats.most_common():
        print(f"  {v:6d}  {k}")
    print(f"  {sum(len(v) for v in plan.values()):6d}  fixes over {len(plan)} files")

    if skipped:
        print("\nleft alone (expression too complex):")
        for s, n in skipped.most_common(args.report):
            print(f"  {n:4d}  {s}")

    if not args.apply:
        print("\n(dry run; pass --apply to write)")
        return 0

    applied = failed = 0
    for path_str, items in plan.items():
        path = Path(path_str)
        if not path.exists():
            failed += len(items)
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        per_line = defaultdict(dict)
        for line_no, col, end, expr, method in items:
            per_line[line_no][col] = (end, expr, method)
        for line_no, positions in per_line.items():
            src = lines[line_no - 1]
            for col in sorted(positions, reverse=True):
                end, expr, method = positions[col]
                if src[col:end] != expr:
                    failed += 1
                    continue
                src = src[:end] + f".{method}()" + src[end:]
                applied += 1
            lines[line_no - 1] = src
        path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\napplied: {applied}  failed: {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
