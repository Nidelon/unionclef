#!/usr/bin/env python3
"""Build a mojmap -> mojmap map between the source version and 26.2.

Renaming yarn names to mojmap gets the source onto the right naming scheme, but
26.x also moved and renamed whole classes: ClickType became ContainerInput,
Skeleton moved into a subpackage, and so on. Learning that one compiler error at
a time is slow.

26.2 ships unobfuscated, so its class files carry the target names directly. The
source version's member names come from Mojang's own proguard mappings, which are
also keyed by the final names. Both sides are therefore reduced to the same
fingerprint: a set of "m:<name>/<arity>" and "f:<name>" strings, and matched by
similarity.

Matching, in order of confidence:
  1. exact fqn            - the class is where it was
  2. unique simple name   - same class, moved package (Skeleton, Sheep, Cow...)
  3. member fingerprint   - same members, different name (ClickType ->
                            ContainerInput), Jaccard >= --apply-min

For every matched pair the members are mapped too, by matching descriptors, so
method renames inside a moved/renamed class come along for free.

Output is written in the shape apply_map.py already consumes:
  {"classes": {old_fqn: new_fqn}, "members": {"old_fqn#member": [new_member]}}

Usage: build_vermap.py --from 1.21.1 --jar <26.2 client jar>
"""
import argparse
import json
import re
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

CP_SIZES = {
    1: None, 3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4,
    15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2,
}

PROGUARD_CLASS_RE = re.compile(r"^(\S+) -> (\S+):$")
PROGUARD_MEMBER_RE = re.compile(r"^(?:\d+:\d+:)?(.+?) -> (\S+)$")

PRIMITIVES = {
    "void": "V", "boolean": "Z", "byte": "B", "char": "C", "short": "S",
    "int": "I", "long": "J", "float": "F", "double": "D",
}


# --------------------------------------------------------------------------- #
# 26.2 side: read names straight out of the class files
# --------------------------------------------------------------------------- #
def count_params(desc):
    if not desc.startswith("("):
        return 0
    end = desc.index(")")
    n = 0
    in_ref = False
    for ch in desc[1:end]:
        if ch == "[":
            continue
        if ch == "L":
            in_ref = True
            continue
        if ch == ";":
            in_ref = False
            n += 1
            continue
        if not in_ref:
            n += 1
    return n


def parse_class(data):
    """-> (this, kind, members) with members as fingerprint strings."""
    if len(data) < 10 or data[:4] != b"\xca\xfe\xba\xbe":
        return None
    pos = 8
    cp_count = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    utf8, class_refs = {}, {}
    i = 1
    while i < cp_count:
        tag = data[pos]
        pos += 1
        if tag == 1:
            length = struct.unpack_from(">H", data, pos)[0]
            pos += 2
            utf8[i] = data[pos:pos + length].decode("utf-8", "replace")
            pos += length
        elif tag == 7:
            class_refs[i] = struct.unpack_from(">H", data, pos)[0]
            pos += 2
        else:
            size = CP_SIZES.get(tag)
            if size is None:
                return None
            pos += size
            if tag in (5, 6):
                i += 1
        i += 1

    def skip_attributes(p):
        count = struct.unpack_from(">H", data, p)[0]
        p += 2
        for _ in range(count):
            length = struct.unpack_from(">I", data, p + 2)[0]
            p += 6 + length
        return p

    access = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    this_idx = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    super_idx = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    iface_count = struct.unpack_from(">H", data, pos)[0]
    pos += 2 + 2 * iface_count

    members = set()
    for prefix in ("f", "m"):  # class files store fields before methods
        count = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        for _ in range(count):
            n_idx = struct.unpack_from(">H", data, pos + 2)[0]
            d_idx = struct.unpack_from(">H", data, pos + 4)[0]
            pos += 6
            pos = skip_attributes(pos)
            name = utf8.get(n_idx, "")
            desc = utf8.get(d_idx, "")
            if name == "<clinit>":
                continue
            if prefix == "m":
                members.add(f"m:{name}/{count_params(desc)}")
            else:
                members.add(f"f:{name}")

    if access & 0x0200:
        kind = "interface"
    elif access & 0x4000:
        kind = "enum"
    else:
        kind = "class"
    this = utf8.get(class_refs.get(this_idx, 0))
    return (this, kind, members)


def read_jar_members(jar):
    """-> {fqn: {"kind":..., "members": set, "by_desc": {desc: name}}}"""
    out = {}
    with zipfile.ZipFile(jar) as z:
        for entry in z.namelist():
            if not entry.endswith(".class"):
                continue
            parsed = parse_class(z.read(entry))
            if parsed is None or parsed[0] is None:
                continue
            this, kind, members = parsed
            out[this.replace("/", ".")] = {
                "kind": kind,
                "members": members,
                "by_desc": read_jar_members_descs(z.read(entry)),
            }
    return out


def read_jar_members_descs(data):
    """Same walk, but keeping descriptors so members can be matched across renames."""
    pos = 8
    cp_count = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    utf8, class_refs = {}, {}
    i = 1
    while i < cp_count:
        tag = data[pos]
        pos += 1
        if tag == 1:
            length = struct.unpack_from(">H", data, pos)[0]
            pos += 2
            utf8[i] = data[pos:pos + length].decode("utf-8", "replace")
            pos += length
        elif tag == 7:
            class_refs[i] = struct.unpack_from(">H", data, pos)[0]
            pos += 2
        else:
            size = CP_SIZES.get(tag)
            if size is None:
                return {}
            pos += size
            if tag in (5, 6):
                i += 1
        i += 1

    def skip_attributes(p):
        count = struct.unpack_from(">H", data, p)[0]
        p += 2
        for _ in range(count):
            length = struct.unpack_from(">I", data, p + 2)[0]
            p += 6 + length
        return p

    pos += 6  # access, this, super
    iface_count = struct.unpack_from(">H", data, pos)[0]
    pos += 2 + 2 * iface_count

    fields, methods = {}, []
    for prefix in ("f", "m"):  # class files store fields before methods
        count = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        for _ in range(count):
            n_idx = struct.unpack_from(">H", data, pos + 2)[0]
            d_idx = struct.unpack_from(">H", data, pos + 4)[0]
            pos += 6
            pos = skip_attributes(pos)
            name = utf8.get(n_idx, "")
            desc = utf8.get(d_idx, "")
            if name == "<clinit>":
                continue
            if prefix == "m":
                methods.append((desc, name))
            else:
                fields[name] = desc
    return {"fields": fields, "methods": methods}


# --------------------------------------------------------------------------- #
# source-version side: member names from Mojang's proguard mappings
# --------------------------------------------------------------------------- #
def java_type_to_desc(t):
    t = t.strip()
    dims = 0
    while t.endswith("[]"):
        dims += 1
        t = t[:-2].strip()
    if t in PRIMITIVES:
        base = PRIMITIVES[t]
    elif re.fullmatch(r"[A-Za-z_$][\w$.$]*", t):
        base = "L" + t.replace(".", "/") + ";"
    else:
        raise ValueError(t)
    return "[" * dims + base


def split_args(args):
    out, depth, cur = [], 0, ""
    for ch in args:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def signature_to_desc(sig):
    """-> (name, desc, is_method) or (None, None, None)."""
    sig = sig.strip()
    if "(" in sig:
        o = sig.index("(")
        c = sig.rindex(")")
        head = sig[:o].strip()
        args = sig[o + 1:c].strip()
        if " " not in head:
            return None, None, None
        ret, name = head.rsplit(" ", 1)
        params = [] if not args else [a.strip() for a in split_args(args)]
        try:
            desc = "(" + "".join(java_type_to_desc(p) for p in params) + ")" \
                   + java_type_to_desc(ret)
        except ValueError:
            return None, None, None
        return name, desc, True
    if " " not in sig:
        return None, None, None
    typ, name = sig.rsplit(" ", 1)
    try:
        return name, java_type_to_desc(typ), False
    except ValueError:
        return None, None, None


def read_old_side(path):
    """-> {mojmap_fqn: {"members": set, "by_desc": {(prefix, desc): name}}}"""
    classes = {}
    members = defaultdict(dict)
    cur_obf = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            line = line.rstrip("\n")
            if not line:
                continue
            if not line.startswith(" "):
                m = PROGUARD_CLASS_RE.match(line)
                if m:
                    cur_obf = m.group(2)
                    classes[cur_obf] = m.group(1)
                continue
            m = PROGUARD_MEMBER_RE.match(line.strip())
            if not (m and cur_obf):
                continue
            name, desc, is_method = signature_to_desc(m.group(1))
            if name is None or m.group(2) in ("<init>", "<clinit>"):
                continue
            if is_method:
                members[cur_obf][("m", desc)] = name
            else:
                # enum constants and other fields share descriptors, so fields
                # must be keyed by name or they collapse into one entry
                members[cur_obf][("f", name)] = desc
    out = {}
    for obf, moj in classes.items():
        by_desc = members.get(obf, {})
        fps = set()
        for (prefix, key), value in by_desc.items():
            if prefix == "m":
                fps.add(f"m:{value}/{count_params(key)}")
            else:
                fps.add(f"f:{key}")
        out[moj] = {"members": fps, "by_desc": by_desc}
    return out


def jaccard(a, b):
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src_ver", required=True)
    ap.add_argument("--jar", required=True, help="unobfuscated 26.2 client jar")
    ap.add_argument("--apply-min", type=float, default=0.90)
    ap.add_argument("--report", type=int, default=12)
    args = ap.parse_args()

    src_dir = HERE / args.src_ver
    old = read_old_side(src_dir / "client.txt")
    new = read_jar_members(Path(args.jar))
    print(f"source mojmap classes ({args.src_ver}): {len(old)}")
    print(f"26.2 classes                        : {len(new)}")

    new_by_simple = defaultdict(list)
    for fqn in new:
        new_by_simple[fqn.rsplit(".", 1)[-1]].append(fqn)

    mapping = {}
    stats = Counter()
    moves = []

    for fqn in old:
        if fqn in new:
            mapping[fqn] = fqn
            stats["exact"] += 1
            continue
        cands = new_by_simple.get(fqn.rsplit(".", 1)[-1], [])
        if len(cands) == 1:
            mapping[fqn] = cands[0]
            stats["simple-name"] += 1
            moves.append((fqn, cands[0], 1.0, "simple-name"))
            continue
        stats["left"] += 1

    # nested pass: a nested class whose outer class is matched is almost always
    # still nested under it, so look only there. This is what pairs
    # BlockPos$Mutable -> BlockPos$MutableBlockPos and
    # ClipContext$FluidHandling -> ClipContext$Fluid, which the global passes miss
    # because the simple names differ.
    for fqn in old:
        if fqn in mapping or "$" not in fqn:
            continue
        outer, _, _inner = fqn.rpartition("$")
        new_outer = mapping.get(outer)
        if not new_outer:
            continue
        cands = [c for c in new if c.startswith(new_outer + "$")
                 and not re.search(r"\$\d+$", c)]
        if not cands:
            continue
        fps = old[fqn]["members"]
        if len(fps) < 2:
            continue
        best, best_score = None, 0.0
        for c in cands:
            score = len(fps & new[c]["members"]) / len(fps)
            if score > best_score:
                best, best_score = c, score
        if best and best_score >= args.apply_min:
            mapping[fqn] = best
            stats["nested"] += 1
            moves.append((fqn, best, best_score, "nested"))

    # fingerprint pass on what is left, via an inverted index over fingerprints
    inv = defaultdict(set)
    for fqn, info in new.items():
        for fp in info["members"]:
            inv[fp].add(fqn)

    for fqn in old:
        if fqn in mapping:
            continue
        fps = old[fqn]["members"]
        if len(fps) < 3:
            stats["too-few-members"] += 1
            continue
        if re.search(r"\$\d+$", fqn):
            stats["anonymous-skipped"] += 1
            continue
        votes = Counter()
        for fp in fps:
            for cand in inv.get(fp, ()):
                votes[cand] += 1
        scored = []
        for cand, shared in votes.most_common(8):
            if shared < 5:
                break
            if re.search(r"\$\d+$", cand):
                continue
            # containment, not Jaccard: a renamed class usually keeps all of its
            # old members and merely gains new ones
            scored.append((len(fps & new[cand]["members"]) / len(fps), cand))
        scored.sort(reverse=True)
        if not scored:
            stats["unmatched"] += 1
            continue
        best_score, best = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        if best_score >= args.apply_min and best_score - runner_up >= 0.05:
            mapping[fqn] = best
            stats["fingerprint"] += 1
            moves.append((fqn, best, best_score, "fingerprint"))
        else:
            stats["unmatched"] += 1

    # member renames inside every matched pair: same descriptor -> new name
    members_out = defaultdict(list)
    for old_fqn, new_fqn in mapping.items():
        if old_fqn == new_fqn:
            continue
        old_m = old[old_fqn]["by_desc"]
        new_m = new[new_fqn]["by_desc"]
        new_methods = {}
        for desc, name in new_m["methods"]:
            new_methods.setdefault(desc, name)
        for (prefix, key), value in old_m.items():
            if prefix == "m":
                # methods are keyed by descriptor, valued by name
                old_name = value
                cand = new_methods.get(key)
            else:
                # fields are keyed by name, valued by descriptor
                old_name = key
                cand = key if key in new_m["fields"] else None
            if cand and cand != old_name:
                mkey = f"{old_fqn}#{old_name}"
                if cand not in members_out[mkey]:
                    members_out[mkey].append(cand)

    # Member renames matched by descriptor alone are NOT auto-applied: both
    # versions have many members of the same shape, so the pairing is often
    # coincidental (Bee#isFlowerValid -> isTooFarAway, PlayerSkin#textureUrl ->
    # toString). They are written to a separate file to consult while fixing
    # compiler errors by hand, and kept out of the map the fixer consumes.
    suggestions = src_dir / "vermap-member-suggestions.json"
    suggestions.write_text(json.dumps(dict(members_out), indent=0), encoding="utf-8")

    dest = src_dir / "vermap.json"
    dest.write_text(json.dumps({
        "classes": mapping,
        "members": {},
        "stats": dict(stats),
    }, indent=0), encoding="utf-8")

    print(f"\nexact fqn matches   : {stats['exact']}")
    print(f"simple-name moves   : {stats['simple-name']}")
    print(f"nested renames      : {stats['nested']}")
    print(f"fingerprint renames : {stats['fingerprint']}")
    print(f"unmatched           : {stats['unmatched']}")
    print(f"member suggestions  : {len(members_out)} (not auto-applied)")
    print(f"written             : {dest}")

    print(f"\nsample moves:")
    for a, b, score, why in moves[:args.report]:
        print(f"  {score:.2f} {why:11s} {a}\n                        -> {b}")

    interesting = [m for m in moves if m[3] == "fingerprint"]
    print(f"\nrename-by-fingerprint sample:")
    for a, b, score, why in interesting[:args.report]:
        print(f"  {score:.2f}  {a}\n        -> {b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
