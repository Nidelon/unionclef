#!/usr/bin/env python3
"""Rewrite 1.21.x per-colour item/block constants into 26.2 colour collections.

In 26.2 the sixteen coloured variants of a family are no longer sixteen separate
constants. Each family is one `ColorCollection<T>` record with a per-colour
accessor:

  Items.WHITE_WOOL          -> Items.WOOL.white()
  Items.RED_DYE             -> Items.DYE.red()
  Blocks.WHITE_WALL_BANNER  -> Blocks.WALL_BANNER.white()
  Items.WHITE_TERRACOTTA    -> Items.DYED_TERRACOTTA.white()

The family list is read from the 26.2 jar rather than hardcoded, so the rewrite
only fires for names that really are collections. Anything that does not resolve
is reported and left alone for a human.

Usage: fix_color_collections.py <src-dir> [--jar <26.2 client jar>] [--apply]
"""
import argparse
import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_JAR = Path.home() / ".gradle/caches/fabric-loom/26.2/minecraft-client.jar"

COLORS = {
    "WHITE": "white", "ORANGE": "orange", "MAGENTA": "magenta",
    "LIGHT_BLUE": "lightBlue", "YELLOW": "yellow", "LIME": "lime",
    "PINK": "pink", "GRAY": "gray", "LIGHT_GRAY": "lightGray",
    "CYAN": "cyan", "PURPLE": "purple", "BLUE": "blue", "BROWN": "brown",
    "GREEN": "green", "RED": "red", "BLACK": "black",
}

HOLDERS = {
    "Items": "net.minecraft.world.item.Items",
    "Blocks": "net.minecraft.world.level.block.Blocks",
}

REF_RE = re.compile(r"\b(Items|Blocks)\.([A-Z][A-Z0-9_]*)\b")


def load_families(jar):
    spec = importlib.util.spec_from_file_location("vm", HERE / "build_vermap.py")
    vm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vm)
    jar_members = vm.read_jar_members(Path(jar))
    families = {}
    for short, fqn in HOLDERS.items():
        info = jar_members.get(fqn)
        if not info:
            continue
        families[short] = {
            name for name, desc in info["by_desc"]["fields"].items()
            if "ColorCollection" in desc
        }
    return families


def resolve(holder, member, families):
    """-> (collection_field, accessor) or None."""
    fam = families.get(holder)
    if not fam:
        return None
    for color, accessor in COLORS.items():
        prefix = color + "_"
        if not member.startswith(prefix):
            continue
        suffix = member[len(prefix):]
        if suffix in fam:
            return suffix, accessor
        if ("DYED_" + suffix) in fam:
            return "DYED_" + suffix, accessor
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--jar", default=str(DEFAULT_JAR))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", type=int, default=25)
    args = ap.parse_args()

    families = load_families(args.jar)
    print("colour collections found in the 26.2 jar:")
    for holder, fam in families.items():
        print(f"  {holder}: {len(fam)} -> {', '.join(sorted(fam))}")

    root = Path(args.src).expanduser().resolve()
    files = sorted(root.rglob("*.java"))
    print(f"\nscanning {len(files)} java files under {root}")

    changed_files = 0
    rewrites = 0
    unresolved = Counter()

    for path in files:
        original = path.read_text(encoding="utf-8")
        text = original
        local = [0]

        def repl(m):
            holder, member = m.group(1), m.group(2)
            got = resolve(holder, member, families)
            if got is None:
                if any(member.startswith(c + "_") for c in COLORS):
                    unresolved[f"{holder}.{member}"] += 1
                return m.group(0)
            field, accessor = got
            local[0] += 1
            return f"{holder}.{field}.{accessor}()"

        text = REF_RE.sub(repl, text)
        if text != original:
            changed_files += 1
            rewrites += local[0]
            if not args.apply:
                pass
            else:
                path.write_text(text, encoding="utf-8")

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"\n[{mode}] files changed : {changed_files}")
    print(f"[{mode}] rewrites      : {rewrites}")
    if unresolved:
        print(f"\ncoloured names with no collection (left alone):")
        for name, n in unresolved.most_common(args.report):
            print(f"  {n:5d}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
