#!/usr/bin/env python3
"""Build a yarn -> mojmap mapping table for the unionclef 26.2 port.

Chain: yarn named -> intermediary -> official(obf) -> mojmap.

Sources (downloaded into this directory):
  yarn.jar            tiny v2, namespaces [intermediary, named]
  inter.jar           tiny v2, namespaces [official, intermediary]
  client_1.21.11.txt  proguard, mojmap signature -> obf name

Members have to be joined on descriptors, not on names: obfuscated member names
are reused for overloads, so a (class, name) key silently collapses a large part
of the table. The two descriptor flavours are reconciled by rendering both in
mojmap JVM form - the obf descriptor by rewriting its class references through
the obf -> mojmap class map, the mojmap signature by parsing it into a
descriptor.

Output: maps.json
  {
    "classes": {yarn_fqn: mojmap_fqn},
    "members": {"<yarn_fqn>#<yarn_member>": [mojmap_member, ...]},
    "stats":   {...}
  }

Members are advisory: they are not applied by the rename pass (no type info),
they exist so compiler errors can be resolved by lookup.
"""
import argparse
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAPS = HERE

PRIMITIVES = {
    "void": "V", "boolean": "Z", "byte": "B", "char": "C", "short": "S",
    "int": "I", "long": "J", "float": "F", "double": "D",
}

PROGUARD_CLASS_RE = re.compile(r"^(\S+) -> (\S+):$")
PROGUARD_MEMBER_RE = re.compile(r"^(?:\d+:\d+:)?(.+?) -> (\S+)$")


def read_tiny(path, ns_a, ns_b):
    """Return (classes, members) for a tiny v2 file.

    classes: {name_in_ns_a: name_in_ns_b}
    members: {(class_ns_a, member_ns_a, desc_ns_a): name_in_ns_b}

    Nested lines carry leading tabs: depth 0 = class, 1 = field/method,
    2 = parameter / local. Only depth 0 and 1 are read.
    """
    classes = {}
    members = {}
    cur = None
    with zipfile.ZipFile(path) as z:
        with z.open("mappings/mappings.tiny") as fh:
            for raw in fh:
                line = raw.decode("utf-8").rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                depth = len(line) - len(line.lstrip("\t"))
                parts = line.lstrip("\t").split("\t")
                tag = parts[0]
                if depth == 0:
                    if tag == "tiny":
                        assert parts[3] == ns_a and parts[4] == ns_b, parts
                    elif tag == "c":
                        cur = parts[1]
                        classes[cur] = parts[2]
                elif depth == 1 and tag in ("f", "m"):
                    # f|m <desc_ns_a> <name_ns_a> <name_ns_b>
                    members[(cur, parts[2], parts[1])] = parts[3]
    return classes, members


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


def java_type_to_desc(t):
    t = t.strip()
    if not t:
        raise ValueError("empty type")
    dims = 0
    while t.endswith("[]"):
        dims += 1
        t = t[:-2].strip()
    if t in PRIMITIVES:
        base = PRIMITIVES[t]
    elif re.fullmatch(r"[A-Za-z_$][\w$.$]*", t):
        base = "L" + t.replace(".", "/") + ";"
    else:
        raise ValueError(f"unparsable type {t!r}")
    return "[" * dims + base


def java_signature_to_desc(sig):
    """`net.minecraft.core.BlockPos add(int,int)` -> ('add', '(II)Lnet/minecraft/core/BlockPos;').

    Proguard signatures are Java-shaped, not JVM descriptors. Returns
    (name, descriptor) or (None, None) when the shape is not recognised.
    """
    sig = sig.strip()
    if "(" in sig:
        open_idx = sig.index("(")
        close_idx = sig.rindex(")")
        head = sig[:open_idx].strip()
        args = sig[open_idx + 1:close_idx].strip()
        if " " not in head:
            return None, None
        ret, name = head.rsplit(" ", 1)
        params = [] if not args else [a.strip() for a in split_args(args)]
        try:
            desc = "(" + "".join(java_type_to_desc(p) for p in params) + ")" \
                   + java_type_to_desc(ret)
        except ValueError:
            return None, None
        return name, desc
    if " " not in sig:
        return None, None
    typ, name = sig.rsplit(" ", 1)
    try:
        return name, java_type_to_desc(typ)
    except ValueError:
        return None, None


def obf_desc_to_moj(desc, moj_classes):
    """Rewrite an obf JVM descriptor into mojmap JVM form."""
    out = []
    i = 0
    while i < len(desc):
        ch = desc[i]
        if ch == "L":
            j = desc.find(";", i)
            if j < 0:
                return None
            name = desc[i + 1:j]
            moj = moj_classes.get(name)
            out.append("L" + (moj.replace(".", "/") if moj else name) + ";")
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def read_proguard(path):
    """Return (classes, members, skipped) mapping obf -> mojmap.

    classes: {obf_class: mojmap_class}
    members: {(obf_class, obf_member, mojmap_desc): mojmap_member}
    """
    classes = {}
    members = {}
    cur_obf = None
    skipped = 0
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
            sig, obf_name = m.group(1), m.group(2)
            if obf_name in ("<init>", "<clinit>"):
                continue
            name, desc = java_signature_to_desc(sig)
            if name is None:
                skipped += 1
                continue
            members[(cur_obf, obf_name, desc)] = name
    return classes, members, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcver", required=True,
                    help="Minecraft version directory under scripts/port/maps/")
    args = ap.parse_args()

    src = MAPS / args.mcver
    if not src.exists():
        print(f"missing mapping sources: {src}", file=sys.stderr)
        return 1

    yarn_cls, yarn_mem = read_tiny(src / "yarn.jar", "intermediary", "named")
    inter_cls, inter_mem = read_tiny(src / "inter.jar", "official", "intermediary")
    moj_cls, moj_mem, moj_skipped = read_proguard(src / "client.txt")

    int2obf = {v: k for k, v in inter_cls.items()}

    classes = {}
    for int_name, yarn_name in yarn_cls.items():
        obf = int2obf.get(int_name)
        if obf is None:
            continue
        moj = moj_cls.get(obf)
        if moj is None:
            continue
        classes[yarn_name] = moj

    # (intermediary class, intermediary member) -> (obf class, obf member, obf desc)
    inv_inter = {}
    for (obf_cls, obf_member, obf_desc), int_member in inter_mem.items():
        int_cls = inter_cls.get(obf_cls)
        if int_cls is None:
            continue
        inv_inter.setdefault((int_cls, int_member), (obf_cls, obf_member, obf_desc))

    members = defaultdict(list)
    miss = defaultdict(int)
    for (int_cls, int_member, _int_desc), yarn_member in yarn_mem.items():
        yarn_cls_name = yarn_cls.get(int_cls)
        if yarn_cls_name is None:
            miss["no-yarn-class"] += 1
            continue
        triple = inv_inter.get((int_cls, int_member))
        if triple is None:
            miss["no-intermediary-link"] += 1
            continue
        obf_cls, obf_member, obf_desc = triple
        moj_desc = obf_desc_to_moj(obf_desc, moj_cls)
        if moj_desc is None:
            miss["bad-desc"] += 1
            continue
        moj_member = moj_mem.get((obf_cls, obf_member, moj_desc))
        if moj_member is None:
            miss["no-mojmap-entry"] += 1
            continue
        key = f"{yarn_cls_name}#{yarn_member}"
        if moj_member not in members[key]:
            members[key].append(moj_member)

    out = {
        "classes": classes,
        "members": dict(members),
        "stats": {
            "mcver": args.mcver,
            "yarn_classes": len(yarn_cls),
            "yarn_members": len(yarn_mem),
            "inter_members": len(inter_mem),
            "moj_members": len(moj_mem),
            "moj_skipped": moj_skipped,
            "mapped_classes": len(classes),
            "mapped_member_keys": len(members),
            "member_misses": dict(miss),
        },
    }
    dest = src / "maps.json"
    dest.write_text(json.dumps(out), encoding="utf-8")

    st = out["stats"]
    print(f"=== {args.mcver}")
    print(f"yarn classes      : {st['yarn_classes']}")
    print(f"yarn members      : {st['yarn_members']}")
    print(f"intermediary mem  : {st['inter_members']}")
    print(f"mojmap members    : {st['moj_members']} (unparsed {st['moj_skipped']})")
    print(f"mapped classes    : {st['mapped_classes']}"
          f"  ({100 * st['mapped_classes'] / st['yarn_classes']:.1f}%)")
    print(f"mapped member keys: {st['mapped_member_keys']}"
          f"  ({100 * st['mapped_member_keys'] / st['yarn_members']:.1f}%)")
    print(f"member misses     : {st['member_misses']}")
    print(f"written           : {dest} ({dest.stat().st_size / 1e6:.1f} MB)")

    print("\nspot checks (classes):")
    for probe in [
        "net/minecraft/client/MinecraftClient",
        "net/minecraft/text/Text",
        "net/minecraft/client/network/ClientPlayerEntity",
        "net/minecraft/client/world/ClientWorld",
        "net/minecraft/util/math/BlockPos",
        "net/minecraft/item/ItemStack",
        "net/minecraft/entity/player/PlayerEntity",
        "net/minecraft/client/gui/screen/Screen",
    ]:
        got = classes.get(probe)
        print(f"  {'OK ' if got else 'MISS'} {probe} -> {got}")

    print("\nspot checks (members):")
    for probe in [
        "net/minecraft/util/math/BlockPos#up",
        "net/minecraft/util/math/BlockPos#add",
        "net/minecraft/client/network/ClientPlayerEntity#getPos",
        "net/minecraft/client/MinecraftClient#world",
        "net/minecraft/text/Text#getString",
    ]:
        got = members.get(probe)
        print(f"  {'OK ' if got else 'MISS'} {probe} -> {got}")


if __name__ == "__main__":
    sys.exit(main())
