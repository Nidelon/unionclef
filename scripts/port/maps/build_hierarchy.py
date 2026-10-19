#!/usr/bin/env python3
"""Build the yarn-named class hierarchy of Minecraft 1.21.11.

javac reports the *static* type of a receiver, but the member it complains about
may be declared in an ancestor (`LocalPlayer#getPos` actually lives on `Entity`).
Without the hierarchy those lookups miss and thousands of renames stay manual.

The hierarchy is read straight out of the obfuscated client jar - only the
constant pool, this_class, super_class and interfaces are needed - then
translated obf -> intermediary -> yarn through the mapping tables.

Output: hierarchy.json  {yarn_fqn: [parent_yarn_fqn, ...]}

Usage: build_hierarchy.py [client.jar]
"""
import argparse
import json
import struct
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

CP_SIZES = {
    1: None,   # Utf8, variable
    3: 4, 4: 4,
    5: 8, 6: 8,   # Long / Double take two slots
    7: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4,
    15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2,
}


def parse_class(data):
    """-> (this_name, super_name, [interface_names]) or None."""
    if len(data) < 10 or data[:4] != b"\xca\xfe\xba\xbe":
        return None
    pos = 8
    cp_count = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    utf8 = {}
    class_refs = {}
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

    pos += 2  # access_flags
    this_idx = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    super_idx = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    iface_count = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    ifaces = []
    for _ in range(iface_count):
        ifaces.append(struct.unpack_from(">H", data, pos)[0])
        pos += 2

    def name_of(idx):
        if idx == 0:
            return None
        return utf8.get(class_refs.get(idx, 0))

    return name_of(this_idx), name_of(super_idx), [name_of(x) for x in ifaces]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mcver", help="Minecraft version directory under scripts/port/maps/")
    ap.add_argument("--jar", help="raw jar to read without translation")
    ap.add_argument("--out", help="output path (with --jar)")
    args = ap.parse_args()

    if args.jar:
        # raw mode: the jar is already unobfuscated (26.2), so no translation is
        # needed and the parents are final names. Used to resolve inherited
        # members against the target version.
        parents = {}
        with zipfile.ZipFile(args.jar) as z:
            for entry in z.namelist():
                if not entry.endswith(".class"):
                    continue
                parsed = parse_class(z.read(entry))
                if parsed is None:
                    continue
                this, sup, ifaces = parsed
                if this is None:
                    continue
                parents[this.replace("/", ".")] = [
                    p.replace("/", ".") for p in ([sup] + ifaces) if p
                ]
        dest = Path(args.out or (HERE / "hierarchy-26.2.json"))
        dest.write_text(json.dumps(parents), encoding="utf-8")
        print(f"classes  : {len(parents)}")
        print(f"written  : {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
        return 0

    if not args.mcver:
        ap.error("either --mcver or --jar is required")
    src = HERE / args.mcver
    jar = src / "client.jar"
    if not jar.exists():
        print(f"missing {jar}", file=sys.stderr)
        return 1

    # reuse the mapping readers so the translation matches build_map.py exactly
    import importlib.util
    spec = importlib.util.spec_from_file_location("bm", HERE / "build_map.py")
    bm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bm)

    yarn_cls, _ = bm.read_tiny(src / "yarn.jar", "intermediary", "named")
    inter_cls, _ = bm.read_tiny(src / "inter.jar", "official", "intermediary")

    obf_parents = {}
    with zipfile.ZipFile(jar) as z:
        for entry in z.namelist():
            if not entry.endswith(".class"):
                continue
            parsed = parse_class(z.read(entry))
            if parsed is None:
                continue
            this, sup, ifaces = parsed
            if this is None:
                continue
            obf_parents[this] = [p for p in ([sup] + ifaces) if p]

    def to_yarn(obf):
        inter = inter_cls.get(obf)
        if inter is None:
            return None
        return yarn_cls.get(inter)

    hierarchy = {}
    unresolved = 0
    for obf, parents in obf_parents.items():
        yarn_name = to_yarn(obf)
        if yarn_name is None:
            unresolved += 1
            continue
        named = []
        for p in parents:
            y = to_yarn(p)
            if y is not None:
                named.append(y)
        hierarchy[yarn_name] = named

    dest = src / "hierarchy.json"
    dest.write_text(json.dumps(hierarchy), encoding="utf-8")
    print(f"classes in jar     : {len(obf_parents)}")
    print(f"translated to yarn : {len(hierarchy)}")
    print(f"untranslated       : {unresolved}")
    print(f"written            : {dest} ({dest.stat().st_size / 1e6:.1f} MB)")

    print("\nspot checks:")
    for probe in [
        "net/minecraft/client/network/ClientPlayerEntity",
        "net/minecraft/client/world/ClientWorld",
        "net/minecraft/util/math/BlockPos",
    ]:
        print(f"  {probe} -> {hierarchy.get(probe)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
