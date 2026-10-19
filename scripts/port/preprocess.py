#!/usr/bin/env python3
"""Materialise one branch of the replaymod-style preprocessor tree.

The canonical tree in `src/` is written for Minecraft 1.21.1: the code for that
version is plain, every other branch is commented out with a `//$$` prefix and
guarded by `//#if MC >= 12111` style directives. javac sees all of it, including
the dead branches, which is why a straight compile drowns in 1.20-era names.

This script evaluates the directives for one target version and writes a plain
tree: the matching branch is un-commented, the rest is commented out.

  preprocess.py <src> <dst> --mc 26020

Version numbering: major*1000 + minor*10 + patch, so 1.21.11 -> 12111 and
26.2 -> 26020. Only the ordering matters: every directive in the tree compares
against a value in the 11605..12111 range, and 26.2 sorts above all of them.

Directives: //#if EXPR | //#elseif EXPR | //#else | //#endif, nestable.
EXPR is `MC <op> <int>` with op in >= <= > < ==.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

DIRECTIVE_RE = re.compile(r"^\s*//#(if|elseif|else|endif)\b\s*(.*)$")
EXPR_RE = re.compile(r"^\s*MC\s*(>=|<=|==|>|<)\s*(\d+)\s*$")
COMMENTED_RE = re.compile(r"^(\s*)//\$\$( ?)(.*)$")

OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


def eval_expr(expr, mc):
    m = EXPR_RE.match(expr)
    if not m:
        raise ValueError(f"cannot parse preprocessor expression: {expr!r}")
    return OPS[m.group(1)](mc, int(m.group(2)))


def uncomment(line):
    m = COMMENTED_RE.match(line)
    if not m:
        return line
    return m.group(1) + m.group(3)


def comment(line):
    if not line.strip():
        return line
    if COMMENTED_RE.match(line):
        return line
    indent = line[: len(line) - len(line.lstrip())]
    return f"{indent}//$$ {line.lstrip()}"


def process_text(text, mc):
    out = []
    # stack of (taken_so_far, active_now)
    stack = []
    stats = {"uncommented": 0, "commented": 0, "directives": 0}

    for line in text.split("\n"):
        d = DIRECTIVE_RE.match(line)
        if d:
            kind, expr = d.group(1), d.group(2)
            stats["directives"] += 1
            if kind == "if":
                val = eval_expr(expr, mc)
                stack.append([val, val])
            elif kind == "elseif":
                if not stack:
                    raise ValueError("//#elseif without //#if")
                top = stack[-1]
                val = (not top[0]) and eval_expr(expr, mc)
                top[0] = top[0] or val
                top[1] = val
            elif kind == "else":
                if not stack:
                    raise ValueError("//#else without //#if")
                top = stack[-1]
                val = not top[0]
                top[0] = True
                top[1] = val
            else:  # endif
                if not stack:
                    raise ValueError("//#endif without //#if")
                stack.pop()
            out.append(line)
            continue

        active = all(frame[1] for frame in stack)
        if active:
            new = uncomment(line)
            if new != line:
                stats["uncommented"] += 1
            out.append(new)
        else:
            new = comment(line)
            if new != line:
                stats["commented"] += 1
            out.append(new)

    if stack:
        raise ValueError(f"unbalanced //#if: {len(stack)} block(s) left open")
    return "\n".join(out), stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--mc", type=int, required=True)
    ap.add_argument("--only", action="append", default=[],
                    help="process only files whose path contains this (repeatable)")
    ap.add_argument("--in-place", action="store_true",
                    help="write into src/ instead of clearing dst first")
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    dst = Path(args.dst).expanduser().resolve()
    if not args.in_place:
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)

    totals = {"uncommented": 0, "commented": 0, "directives": 0, "files": 0}
    for path in sorted(src.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        if args.only and not any(o in str(rel) for o in args.only):
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix != ".java":
            shutil.copy2(path, target)
            continue
        text = path.read_text(encoding="utf-8")
        new, stats = process_text(text, args.mc)
        target.write_text(new, encoding="utf-8")
        totals["files"] += 1
        for k in ("uncommented", "commented", "directives"):
            totals[k] += stats[k]

    print(f"target MC        : {args.mc}")
    print(f"java files       : {totals['files']}")
    print(f"directives seen  : {totals['directives']}")
    print(f"lines uncommented: {totals['uncommented']}")
    print(f"lines commented  : {totals['commented']}")
    print(f"written          : {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
