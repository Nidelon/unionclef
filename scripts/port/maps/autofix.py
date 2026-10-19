#!/usr/bin/env python3
"""Fix port errors from structured javac diagnostics.

Consumes build/diag.jsonl (scripts/port/diag/run.sh) instead of parsing javac's text
output: every record carries the exact [start, end) range of the offending
symbol, so nothing has to be re-derived from a caret column.

Rules, by diagnostic code:

  cant.resolve.location[.args]  symbol: class X
      -> class rename/move: resolved through the composed map, then looked up in
         the 26.2 jar by simple name within the same outer class
  cant.resolve.location[.args]  symbol: method/field X
      -> member rename: composed map, then the class hierarchy, then a global
         name index; overloads are separated by the call's argument count
  prob.found.req  "Direction cannot be converted to Vec3i/Vec3"
      -> wrap the expression in .getUnitVec3i() / .getUnitVec3()

Everything else is reported with its exact location for a human decision.

Usage: autofix.py [--diag build/diag.jsonl] [--apply] [--report N]
"""
import argparse
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(HERE))
import fix_members as fm  # noqa: E402

JAR_26 = Path.home() / ".gradle/caches/fabric-loom/26.2/minecraft-client.jar"

SYM_RE = re.compile(r"symbol:\s+(?:(?P<kind>\w+)\s+)?(?P<name>\S+)")
LOC_RE = re.compile(r"location:\s+(?:(?P<kind>\w+)\s+)?(?P<name>\S+)")


def load_jar_members(path):
    spec = importlib.util.spec_from_file_location("vm", HERE / "build_vermap.py")
    vm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vm)
    return vm.read_jar_members(Path(path))


def parse_message(msg):
    sym_kind = sym_name = loc_kind = loc_name = None
    m = SYM_RE.search(msg)
    if m:
        sym_kind = m.group("kind") or "class"
        sym_name = m.group("name").split("(")[0]
    m = LOC_RE.search(msg)
    if m:
        loc_kind = m.group("kind") or "class"
        loc_name = m.group("name").rstrip(".")
        loc_name = re.sub(r"<.*>$", "", loc_name)
        if loc_kind == "variable":
            tm = re.search(r"of type\s+([^\s]+)", msg)
            loc_name = tm.group(1).split("<")[0] if tm else None
    return sym_kind, sym_name, loc_kind, loc_name


def call_arity(text, end):
    """Argument count of the call starting just after `end`, or None."""
    i = end
    n = len(text)
    while i < n and text[i] in " \t":
        i += 1
    if i >= n or text[i] != "(":
        return None
    depth = 0
    args = 0
    has_content = False
    while i < n:
        c = text[i]
        if c in "([{":
            depth += 1
            if depth == 1:
                i += 1
                continue
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return 0 if not has_content else args + 1
        elif c == "," and depth == 1:
            args += 1
        elif depth == 1 and not c.isspace():
            has_content = True
        i += 1
    return None


def enclosing_call_name(text, pos):
    """Name of the call whose argument list contains `pos`, or None."""
    depth = 0
    i = pos - 1
    while i >= 0:
        c = text[i]
        if c in ")]}":
            depth += 1
        elif c in "([{":
            if depth == 0:
                j = i - 1
                while j >= 0 and text[j] in " \t":
                    j -= 1
                k = j
                while k >= 0 and (text[k].isalnum() or text[k] in "_$"):
                    k -= 1
                return text[k + 1:j + 1] or None, k + 1
            depth -= 1
        elif c == ";" and depth == 0:
            return None, None
        i -= 1
    return None, None


def receiver_start(text, dot_pos):
    """Start offset of the expression ending just before `dot_pos` (a '.')."""
    i = dot_pos - 1
    depth = 0
    while i >= 0:
        c = text[i]
        if c in ")]}":
            depth += 1
        elif c in "([{":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and not (c.isalnum() or c in "_$."):
            break
        i -= 1
    return i + 1


def owner_chain(hierarchy, fqn):
    """fqn plus all its ancestors in the 26.2 hierarchy."""
    seen, queue, out = set(), [fqn], []
    while queue:
        c = queue.pop(0)
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
        queue.extend(hierarchy.get(c, []))
    return out


def call_end(text, end):
    """Offset just past the closing paren of the call whose name ends at `end`."""
    i = end
    n = len(text)
    while i < n and text[i] in " \t":
        i += 1
    if i >= n or text[i] != "(":
        return None
    depth = 0
    while i < n:
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def apply_rules(rules, text, start, end, sym_name, owner_chain_set, jar_members,
                hierarchy):
    """Try the override table; return (new_text, why) or (None, None)."""
    # Only explicit receivers: an unqualified `getNormal()` is a call on `this`,
    # whose type is the enclosing class, not the rule's owner. Rewriting those
    # renames local helper methods and breaks working code.
    if not text[:start].rstrip().endswith("."):
        return None, None
    for r in rules:
        if r["old"] != sym_name:
            continue
        if r["owner"] not in owner_chain_set:
            continue
        if r.get("field"):
            return r["new"], f"rule:{r['owner'].rsplit('.', 1)[-1]}#{r['old']}"
        if r.get("one-arg"):
            ce = call_end(text, end)
            if ce is None:
                continue
            inner = text[end:ce]
            if inner.count(",") != 0:
                continue
            return r["new"], f"rule:{r['old']}->{r['new']}(1)"
        if r.get("args") is not None:
            ce = call_end(text, end)
            if ce is None:
                continue
            return f"{r['new']}({r['args']})", f"rule:{r['old']}->{r['new']}"
        return r["new"], f"rule:{r['old']}->{r['new']}"
    return None, None


def class_member_names(jar_members, hierarchy, fqn, want_methods):
    """Names of methods (or fields) visible on fqn, walking the 26.2 hierarchy."""
    out = set()
    seen = set()
    queue = [fqn]
    while queue:
        cls = queue.pop(0)
        if cls in seen:
            continue
        seen.add(cls)
        info = jar_members.get(cls)
        if info:
            if want_methods:
                out.update(name for _, name in info["by_desc"]["methods"])
            else:
                out.update(info["by_desc"]["fields"])
        queue.extend(hierarchy.get(cls, []))
    return out


def find_candidates(members, hierarchy, yarn_owner, name):
    """Walk the hierarchy to the declaring class; return (class, candidates)."""
    seen = set()
    queue = [yarn_owner]
    while queue:
        cls = queue.pop(0)
        if cls in seen:
            continue
        seen.add(cls)
        cands = members.get(f"{cls}#{name}")
        if cands:
            return cls, cands
        queue.extend(hierarchy.get(cls, []))
    return None, None


def class_arity_index(jar_members, hierarchy, fqn):
    """member name -> set of arities, walking the 26.2 hierarchy.

    Members are usually declared on an ancestor (LocalPlayer#getYRot lives on
    Entity), so the index has to follow the parent chain or every inherited
    overload looks unresolvable.
    """
    out = defaultdict(set)
    seen = set()
    queue = [fqn]
    while queue:
        cls = queue.pop(0)
        if cls in seen:
            continue
        seen.add(cls)
        info = jar_members.get(cls)
        if info:
            for desc, name in info["by_desc"]["methods"]:
                args = desc[1:desc.index(")")] if desc.startswith("(") else ""
                out[name].add(0 if not args else args.count(",") + 1)
        queue.extend(hierarchy.get(cls, []))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diag", default=str(REPO / "port26/build/diag.jsonl"))
    ap.add_argument("--map-12101", default=str(HERE / "1.21.1/composed.json"))
    ap.add_argument("--map-12111", default=str(HERE / "1.21.11/composed.json"))
    ap.add_argument("--hier-12101", default=str(HERE / "1.21.1/hierarchy.json"))
    ap.add_argument("--hier-12111", default=str(HERE / "1.21.11/hierarchy.json"))
    ap.add_argument("--jar", default=str(JAR_26))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", type=int, default=20)
    args = ap.parse_args()

    per_tree = {}
    for tag, mapfile, hierfile in (
        ("adris", args.map_12101, args.hier_12101),
        ("kaptainwutax", args.map_12111, args.hier_12111),
    ):
        classes, members, rev, simple, global_index = fm.load_maps(mapfile)
        hierarchy = fm.load_hierarchy(hierfile)
        per_tree[tag] = (members, rev, simple, global_index, hierarchy)

    jar_members = load_jar_members(args.jar)
    jar_hierarchy = json.loads((HERE / "hierarchy-26.2.json").read_text(encoding="utf-8"))
    rules = json.loads((HERE / "overrides.json").read_text(encoding="utf-8"))
    class_rules = {r["class"]: r["new"] for r in
                   json.loads((HERE / "class_overrides.json").read_text(encoding="utf-8"))}
    entries = [json.loads(l) for l in open(args.diag)]
    print(f"diagnostics: {len(entries)}")

    text_cache = {}
    import_cache = {}
    plan = defaultdict(list)   # file -> [(start, end, new_text, why)]
    stats = Counter()
    unresolved = Counter()

    def tree_of(path):
        for tag in per_tree:
            if f"/{tag}/" in path:
                return tag
        return None

    for e in entries:
        path = e["file"]
        start, end = e["start"], e["end"]
        code = e["code"]
        if start < 0 or end < 0 or start >= end:
            stats["skip:no-span"] += 1
            continue
        if path not in text_cache:
            text_cache[path] = Path(path).read_text(encoding="utf-8")
        text = text_cache[path]
        span = text[start:end]
        msg = e["message"]
        tag = tree_of(path)

        # javac spans a qualified invocation as `receiver.method`, while the
        # symbol is only the trailing name. Replacing the whole span would drop
        # the receiver, so narrow it to the symbol itself.
        sym_probe = SYM_RE.search(msg)
        if sym_probe:
            nm = sym_probe.group("name").split("(")[0]
            kind = sym_probe.group("kind") or "class"
            if kind in ("method", "variable") and len(span) > len(nm) \
                    and span.endswith(nm):
                start = end - len(nm)
                span = nm

        if code.startswith("compiler.err.cant.resolve") and span.endswith("toCenterPos"):
            dot = end - len("toCenterPos") - 1
            if dot >= 0 and text[dot] == ".":
                rs = receiver_start(text, dot)
                recv = text[rs:dot]
                ce = call_end(text, end)
                if recv and ce is not None:
                    plan[path].append((rs, ce, f"Vec3.atCenterOf({recv})",
                                       "rule:toCenterPos"))
                    stats["rule:toCenterPos"] += 1
                    continue

        if code.startswith("compiler.err.cant.resolve") or code == "compiler.err.cant.resolve":
            sym_kind, sym_name, loc_kind, loc_name = parse_message(msg)
            if not sym_name:
                stats["skip:unparsed-message"] += 1
                continue
            if sym_kind == "class":
                simple = span.rsplit(".", 1)[-1]
                if simple in class_rules:
                    new = class_rules[simple]
                    plan[path].append((end - len(simple), end, new,
                                       f"class:{simple}->{new}"))
                    stats["class-rule"] += 1
                    continue
                stats["class-symbol"] += 1
                unresolved[f"class {simple} @ {loc_name}"] += 1
                continue
            if sym_name in class_rules:
                new = class_rules[sym_name]
                plan[path].append((end - len(sym_name), end, new,
                                   f"class:{sym_name}->{new}"))
                stats["class-rule"] += 1
                continue
            if tag is None:
                stats["skip:no-tree"] += 1
                continue
            members, rev, simple_idx, global_index, hierarchy = per_tree[tag]
            if loc_name is None:
                stats["skip:no-location"] += 1
                unresolved[f"None#{sym_name}"] += 1
                continue
            if "." in loc_name:
                # javac already printed the fully qualified owner
                moj_owner = loc_name
            else:
                moj_owner = fm.file_imports(path, import_cache).get(loc_name)
                if moj_owner is None:
                    owners = simple_idx.get(loc_name)
                    if not owners or len(owners) > 1:
                        stats["skip:owner-unresolved"] += 1
                        unresolved[f"{loc_name}#{sym_name}"] += 1
                        continue
                    moj_owner = next(iter(owners))
            yarn_owner = rev.get(moj_owner)
            if yarn_owner is None:
                stats["skip:owner-unmapped"] += 1
                continue
            chain = owner_chain(jar_hierarchy, moj_owner)
            rule_text, rule_why = apply_rules(rules, text, start, end, sym_name,
                                              set(chain), jar_members, jar_hierarchy)
            if rule_text is not None:
                if rule_text.endswith(")") and not rule_text.endswith("()"):
                    # a rule that supplies arguments consumes the existing call
                    ce = call_end(text, end)
                    if ce is not None:
                        end = ce
                plan[path].append((start, end, rule_text, rule_why))
                stats[f"rule:{rule_why.split(':')[1]}"] += 1
                continue

            decl_cls, cands = find_candidates(members, hierarchy, yarn_owner,
                                              sym_name)
            cand, source = None, None
            if decl_cls is None:
                g = global_index.get(sym_name)
                if g and len(g) == 1:
                    cand, source = next(iter(g)), "global"
                else:
                    source = "no-member-entry" if not g else "global-ambiguous"
            elif len(cands) == 1:
                cand, source = cands[0], "class"
            else:
                # overloads: separate them by the call's argument count, walking
                # the 26.2 hierarchy because the member may be declared on an
                # ancestor
                arity = call_arity(text, end)
                if arity is not None:
                    arities = class_arity_index(jar_members, jar_hierarchy,
                                                moj_owner)
                    fits = [c for c in cands if arity in arities.get(c, set())]
                    if len(fits) == 1:
                        cand, source = fits[0], "arity"
                if cand is None:
                    source = "member-ambiguous"
            if cand is None:
                stats[f"skip:{source}"] += 1
                unresolved[f"{loc_name}#{sym_name}"] += 1
                continue
            # The candidate comes from the SOURCE version's mappings, and 26.2
            # renamed things again: getYaw -> getYRot is right for 1.21.1 mojmap
            # but 26.2 has no Entity.getYRot. Applying it would just churn the
            # error into a different name, so verify against the 26.2 jar first.
            want_methods = sym_kind != "variable"
            names = class_member_names(jar_members, jar_hierarchy, moj_owner,
                                       want_methods)
            if cand not in names:
                stats["skip:candidate-missing-in-26.2"] += 1
                unresolved[f"{loc_name}#{sym_name} -> {cand} (gone in 26.2)"] += 1
                continue
            plan[path].append((start, end, cand, source))
            stats[f"member:{source}"] += 1
            continue

        if code == "compiler.err.report.access":
            m = re.match(r"(\w+) has private access in (\S+)", msg)
            if m:
                sym_name, moj_owner = m.group(1), m.group(2)
                if len(span) > len(sym_name) and span.endswith(sym_name):
                    start = end - len(sym_name)
                    span = sym_name
                chain = set(owner_chain(jar_hierarchy, moj_owner))
                rule_text, rule_why = apply_rules(
                    rules, text, start, end, sym_name, chain, jar_members,
                    jar_hierarchy)
                if rule_text is not None:
                    plan[path].append((start, end, rule_text, rule_why))
                    stats[f"rule:{rule_why.split(':')[1]}"] += 1
                    continue
            stats["other:access"] += 1
            continue

        if code == "compiler.err.prob.found.req":
            m = re.search(r"incompatible types:\s*(\w[\w.]*)\s+cannot be converted to\s+(\w[\w.]*)", msg)
            if m and m.group(2).endswith("Vec3") and m.group(1) in ("double", "float", "int"):
                name, nstart = enclosing_call_name(text, start)
                if name == "multiply":
                    plan[path].append((nstart, nstart + len(name), "scale",
                                       "rule:multiply->scale(1)"))
                    stats["rule:multiply->scale"] += 1
                    continue
            if m and m.group(1).rsplit(".", 1)[-1] == "Vec3" \
                    and m.group(2).rsplit(".", 1)[-1] == "Vec3i":
                plan[path].append((start, end, f"BlockPos.containing({span})",
                                   "wrap:vec3->vec3i"))
                stats["wrap:vec3->vec3i"] += 1
                continue
            if m and m.group(1).rsplit(".", 1)[-1] == "Direction" \
                    and m.group(2).rsplit(".", 1)[-1] == "long":
                name, nstart = enclosing_call_name(text, start)
                if name == "offset":
                    plan[path].append((nstart, nstart + len(name), "relative",
                                       "rule:offset->relative"))
                    stats["rule:offset->relative"] += 1
                    continue
            if m and m.group(1).rsplit(".", 1)[-1] == "Direction" \
                    and m.group(2).rsplit(".", 1)[-1] in ("Vec3i", "Vec3"):
                name, nstart = enclosing_call_name(text, start)
                if name == "offset":
                    plan[path].append((nstart, nstart + len(name), "relative",
                                       "rule:offset->relative"))
                    stats["rule:offset->relative"] += 1
                    continue
                method = ("getUnitVec3i" if m.group(2).rsplit(".", 1)[-1] == "Vec3i"
                          else "getUnitVec3")
                if text[start:end] and f".{method}()" not in text[start:end]:
                    plan[path].append((start, end, text[start:end] + f".{method}()",
                                       "direction-conversion"))
                    stats["conversion:direction"] += 1
                    continue
            stats["other:found.req"] += 1
            continue

        if code == "compiler.err.cant.apply.symbol" and "contract" in msg \
                and "AABB" in msg:
            # the span covers the whole invocation, receiver included
            ce = call_end(text, end)
            if ce is not None:
                # end sits right after the method name, so the opening paren is
                # at text[end]; args run from end+1 to just before the closer
                arg = text[end + 1:ce - 1].strip()
                if arg and "," not in arg and not arg.startswith("("):
                    plan[path].append((end - len("contract"), ce,
                                       f"contract({arg}, {arg}, {arg})",
                                       "rule:contract(1)->contract(3)"))
                    stats["rule:contract-3"] += 1
                    continue

        if code in ("compiler.err.cant.apply.symbol",
                    "compiler.err.cant.apply.symbols") \
                and "getEntities" in msg and "no arguments" in msg:
            ce = call_end(text, end)
            if ce is not None:
                plan[path].append((end - len("getEntities"), ce,
                                   "entitiesForRendering()",
                                   "rule:getEntities->entitiesForRendering"))
                stats["rule:getEntities"] += 1
                continue

        if code == "compiler.err.cant.deref" and "getId(" in span:
            rel = span.index("getId(")
            plan[path].append((start + rel, start + rel + 5, "getKey",
                               "rule:getId->getKey"))
            stats["rule:getId->getKey"] += 1
            continue

        stats[f"other:{code.rsplit('.', 1)[-1]}"] += 1

    print("\n=== plan ===")
    for k, v in stats.most_common():
        print(f"  {v:6d}  {k}")
    total = sum(len(v) for v in plan.values())
    print(f"  {total:6d}  fixes over {len(plan)} files")

    if unresolved:
        print("\n=== unresolved (top) ===")
        for k, v in unresolved.most_common(args.report):
            print(f"  {v:5d}  {k}")

    if not args.apply:
        print("\n(dry run; pass --apply to write)")
        return 0

    applied = failed = 0
    for path, items in plan.items():
        text = Path(path).read_text(encoding="utf-8")
        # dedupe by span, apply right-to-left so offsets stay valid
        by_span = {}
        for start, end, new, why in items:
            by_span[(start, end)] = (new, why)
        lowest = None
        for (start, end) in sorted(by_span, reverse=True):
            new, why = by_span[(start, end)]
            # right-to-left: any span reaching past the last applied one would
            # overwrite a fix that is already in place
            if lowest is not None and end > lowest:
                stats["skip:overlap"] += 1
                continue
            if not text[start:end]:
                failed += 1
                continue
            text = text[:start] + new + text[end:]
            lowest = start
            applied += 1
        Path(path).write_text(text, encoding="utf-8")

    print(f"\napplied: {applied}  failed: {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
