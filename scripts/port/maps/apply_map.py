#!/usr/bin/env python3
"""Apply the yarn -> mojmap rename to a source tree.

Passes per file:

0. Wildcard imports - `import net.minecraft.util.math.*;` cannot survive the
   rename (that package does not exist in mojmap), so it is expanded into
   explicit imports for the classes the file actually uses.

1. FQN pass - any `net.minecraft....` dotted name that resolves in the class map
   is rewritten. Nested classes are resolved by splitting the tail with `$`
   (source writes `a.b.Outer.Inner`, mappings store `a/b/Outer$Inner`), and a
   trailing member is carried over untouched
   (`net.minecraft.item.Items.SHEARS` -> `net.minecraft.world.item.Items.SHEARS`).

2. Simple-name pass - for every import that points at a mapped class the local
   simple name changes (Text -> Component, MinecraftClient -> Minecraft). The
   rename is applied file-wide with word boundaries, but only when it is
   unambiguous: skipped if the file declares its own type with that name, or if
   two imports want the same old simple name to become different things.

Members (methods/fields) are deliberately NOT renamed: without type information
that is guesswork. They are resolved afterwards from compiler errors, with
maps.json["members"] as the lookup table.

Usage:
  apply_map.py <src-dir> [--dry-run] [--verbose]
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_MAP = HERE / "1.21.11" / "maps.json"

FQN_RE = re.compile(r"\b(?:net\.minecraft|com\.mojang)\.[A-Za-z0-9_$.]+")
IMPORT_RE = re.compile(r"^[ \t]*import\s+(static\s+)?([A-Za-z0-9_$.]+)[ \t]*;[ \t]*$", re.M)
WILDCARD_RE = re.compile(r"^([ \t]*)import\s+([A-Za-z0-9_$.]+)\.\*;[ \t]*$", re.M)
TYPE_DECL_RE = re.compile(
    r"\b(?:class|interface|enum|record|@interface)\s+([A-Z]\w*)"
)


def load_maps(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["classes"], data.get("members", {})


def build_lookup(classes):
    """dotted source name -> dotted mojmap name.

    Keys keep the mappings' '$' nesting separator so a candidate can be
    assembled unambiguously; values are converted to source form on return.
    """
    lookup = {}
    for yarn, moj in classes.items():
        lookup[yarn.replace("/", ".")] = moj.replace("/", ".")
    return lookup


def build_packages(classes):
    """yarn package -> {yarn simple name: mojmap dotted fqn} (top level types only)."""
    pkgs = defaultdict(dict)
    for yarn, moj in classes.items():
        if "$" in yarn:
            continue
        pkg, _, simple = yarn.rpartition("/")
        pkgs[pkg.replace("/", ".")][simple] = moj.replace("/", ".")
    return dict(pkgs)


def build_nested(classes):
    """yarn outer fqn -> [(yarn inner simple, mojmap outer simple, mojmap inner simple)].

    Only pairs where the INNER name changes: when just the outer is renamed the
    ordinary simple-name pass already fixes `OldOuter.Inner` -> `NewOuter.Inner`,
    but `BlockPos.Mutable` -> `BlockPos.MutableBlockPos` needs this table because
    `Mutable` is never imported on its own line.
    """
    nested = defaultdict(list)
    for yarn, moj in classes.items():
        if "$" not in yarn:
            continue
        yarn_outer, _, yarn_inner = yarn.partition("$")
        moj_outer, _, moj_inner = moj.partition("$")
        if yarn_inner == moj_inner:
            continue
        entry = (yarn_inner, moj_outer.rsplit("/", 1)[-1], moj_inner)
        # registered under both the yarn and the mojmap outer name so the pass
        # works whether it runs before or after the FQN rename
        nested[yarn_outer].append(entry)
        nested[moj_outer.replace(".", "/")].append(entry)
    return dict(nested)


def rename_nested(text, imports, nested, lookup, verbose_log):
    """Rewrite `Outer.Inner` where the inner class was renamed."""
    hits = 0
    for _, is_static, fqn in imports:
        if is_static:
            continue
        entries = nested.get(fqn.replace(".", "/"))
        if not entries:
            continue
        old_outer_simple = fqn.rsplit(".", 1)[-1]
        for inner, new_outer_simple, new_inner in entries:
            pat = re.compile(
                rf"(?<![\w$.]){re.escape(old_outer_simple)}\.{re.escape(inner)}(?![\w$])")
            text, n = pat.subn(f"{new_outer_simple}.{new_inner}", text)
            if n:
                hits += n
                verbose_log(f"    nested {old_outer_simple}.{inner} -> "
                            f"{new_outer_simple}.{new_inner} x{n}")
    return text, hits


def resolve(dotted, lookup):
    """Resolve a dotted name that may end in nested classes or members.

    Returns (mojmap_fqn_in_source_form, trailing_suffix) or (None, None):
      net.minecraft.item.Items.SHEARS -> ('net.minecraft.world.item.Items', '.SHEARS')
      a.b.Outer.Inner                -> mojmap of the nested class, ''
    """
    parts = dotted.split(".")
    for cut in range(len(parts), 2, -1):
        head = ".".join(parts[:cut])
        tail = parts[cut:]
        if tail:
            joined = head + "$" + "$".join(tail)
            if joined in lookup:
                return lookup[joined].replace("$", "."), ""
        if head in lookup:
            suffix = ("." + ".".join(tail)) if tail else ""
            return lookup[head].replace("$", "."), suffix
    return None, None


def rename_fqns(text, lookup):
    hits = 0

    def sub(m):
        nonlocal hits
        got, suffix = resolve(m.group(0), lookup)
        if got is None:
            return m.group(0)
        hits += 1
        return got + suffix

    return FQN_RE.sub(sub, text), hits


def collect_imports(text):
    out = []
    for m in IMPORT_RE.finditer(text):
        out.append((m.group(0), bool(m.group(1)), m.group(2)))
    return out


def expand_wildcards(text, packages, own_types, already_imported, verbose_log):
    """Replace `import pkg.*;` with explicit imports of the classes actually used.

    Yarn packages do not survive the rename (net.minecraft.util.math.* splits into
    net.minecraft.core / net.minecraft.world.phys), so a wildcard has to be
    resolved member by member. Returns (text, deltas).
    """
    deltas = {}
    body = IMPORT_RE.sub("", text)
    body = WILDCARD_RE.sub("", body)

    def repl(m):
        indent, pkg = m.group(1), m.group(2)
        members = packages.get(pkg)
        if members is None:
            return m.group(0)  # not a mapped package, leave it alone
        used = []
        for old_simple, moj_fqn in sorted(members.items()):
            if old_simple in own_types:
                continue
            if not re.search(rf"(?<![\w$.]){re.escape(old_simple)}(?![\w$])", body):
                continue
            if old_simple in already_imported:
                verbose_log(f"    wildcard {pkg}: skip {old_simple} (imported elsewhere)")
                continue
            used.append((old_simple, moj_fqn))
        if not used:
            return ""  # nothing from this package is used, drop the line
        lines = []
        for old_simple, moj_fqn in used:
            lines.append(f"{indent}import {moj_fqn};")
            new_simple = moj_fqn.rsplit(".", 1)[-1]
            if old_simple != new_simple and old_simple not in deltas:
                deltas[old_simple] = new_simple
        return "\n".join(lines)

    return WILDCARD_RE.sub(repl, text), deltas


def simple_deltas(imports, lookup):
    """old simple name -> new simple name, from the import block."""
    deltas = {}
    conflicts = set()
    for _, is_static, fqn in imports:
        if is_static:
            # import static a.b.C.member; - the member itself is not renamed here
            continue
        target, suffix = resolve(fqn, lookup)
        if target is None:
            continue
        old = fqn.rsplit(".", 1)[-1]
        new = (target + suffix).rsplit(".", 1)[-1]
        if old == new:
            continue
        if old in deltas and deltas[old] != new:
            conflicts.add(old)
            continue
        deltas[old] = new
    for name in conflicts:
        deltas.pop(name, None)
    return deltas, conflicts


def apply_simple(text, deltas, own_types, verbose_log):
    hits = 0
    for old, new in sorted(deltas.items(), key=lambda kv: -len(kv[0])):
        if old in own_types:
            verbose_log(f"    skip {old} (declared in file)")
            continue
        pat = re.compile(rf"(?<![\w$.]){re.escape(old)}(?![\w$])")
        text, n = pat.subn(new, text)
        hits += n
    return text, hits


def rewrite_imports(text, lookup):
    """Rewrite the FQN inside import statements (including static ones)."""
    def repl(m):
        fqn = m.group(2)
        if m.group(1):
            cls, _, member = fqn.rpartition(".")
            target, suffix = resolve(cls, lookup)
            if target is None:
                return m.group(0)
            return f"import static {target}{suffix}.{member};"
        target, suffix = resolve(fqn, lookup)
        if target is None:
            return m.group(0)
        return f"import {target}{suffix};"

    return IMPORT_RE.sub(repl, text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--map", default=str(DEFAULT_MAP),
                    help="maps.json to use (per Minecraft version)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    classes, _members = load_maps(args.map)
    lookup = build_lookup(classes)
    packages = build_packages(classes)
    nested = build_nested(classes)
    print(f"map: {args.map}")
    print(f"class map: {len(classes)} entries ({len(lookup)} dotted forms), "
          f"{len(packages)} packages")

    root = Path(args.src).expanduser().resolve()
    files = sorted(root.rglob("*.java"))
    print(f"scanning {len(files)} java files under {root}\n")

    changed_files = 0
    fqn_hits = simple_hits = import_files = wildcard_files = nested_hits = 0
    skipped_conflicts = defaultdict(int)

    def vlog(msg):
        if args.verbose:
            print(msg)

    for path in files:
        original = path.read_text(encoding="utf-8")
        text = original

        imports = collect_imports(text)
        own_types = set(TYPE_DECL_RE.findall(text))
        already_imported = {
            fqn.rsplit(".", 1)[-1] for _, is_static, fqn in imports if not is_static
        }

        # pass 0: expand mapped wildcard imports into explicit ones
        had_wildcard = bool(WILDCARD_RE.search(text))
        text, wc_deltas = expand_wildcards(
            text, packages, own_types, already_imported, vlog
        )
        if had_wildcard and text != original:
            wildcard_files += 1

        # pass 1: import lines (nesting aware), then bare FQNs in the body
        before_imports = text
        text = rewrite_imports(text, lookup)
        if text != before_imports:
            import_files += 1
        text, n_fqn = rename_fqns(text, lookup)

        # pass 2: simple names
        deltas, conflicts = simple_deltas(imports, lookup)
        for name, new in wc_deltas.items():
            deltas.setdefault(name, new)
        for c in conflicts:
            skipped_conflicts[c] += 1
        text, n_simple = apply_simple(text, deltas, own_types, vlog)

        # pass 3: nested class renames written as Outer.Inner
        text, n_nested = rename_nested(text, imports, nested, lookup, vlog)

        if text != original:
            changed_files += 1
            fqn_hits += n_fqn
            simple_hits += n_simple
            nested_hits += n_nested
            if args.verbose:
                print(f"  {path.relative_to(root)}: {n_fqn} fqn, {n_simple} simple")
            if not args.dry_run:
                path.write_text(text, encoding="utf-8")

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"\n[{mode}] files scanned    : {len(files)}")
    print(f"[{mode}] files changed    : {changed_files}")
    print(f"[{mode}] wildcard files   : {wildcard_files}")
    print(f"[{mode}] import files     : {import_files}")
    print(f"[{mode}] fqn rewrites     : {fqn_hits}")
    print(f"[{mode}] simple renames   : {simple_hits}")
    print(f"[{mode}] nested renames   : {nested_hits}")
    if skipped_conflicts:
        print(f"[{mode}] ambiguous simple names skipped: {dict(skipped_conflicts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
