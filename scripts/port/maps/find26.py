#!/usr/bin/env python3
"""Look up where a member or class went in the 26.2 jar.

Working the remaining port errors means answering the same question over and
over: "this member is gone from this class, where is it now?". This is the
lookup tool for that.

  find26.py --member getValue --owner BlockState     # who declares getValue
  find26.py --member setScreen                        # anywhere in the jar
  find26.py --class Mutable --like BlockPos           # nested class renames
  find26.py --fields --owner Minecraft --match screen

Usage: find26.py [--jar JAR] <one of the modes>
"""
import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_JAR = Path.home() / ".gradle/caches/fabric-loom/26.2/minecraft-client.jar"


def load(jar):
    spec = importlib.util.spec_from_file_location("vm", HERE / "build_vermap.py")
    vm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vm)
    return vm.read_jar_members(Path(jar))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", default=str(DEFAULT_JAR))
    ap.add_argument("--member", help="member name to search for")
    ap.add_argument("--owner", help="restrict to this class (simple or fqn)")
    ap.add_argument("--class", dest="cls", help="class simple name to search for")
    ap.add_argument("--like", help="restrict class search to fqns containing this")
    ap.add_argument("--fields", action="store_true", help="search fields, not methods")
    ap.add_argument("--match", help="substring filter on member names")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    jar = load(args.jar)
    print(f"jar: {args.jar} ({len(jar)} classes)")

    if args.cls:
        hits = [n for n in sorted(jar)
                if n.rsplit(".", 1)[-1].split("$")[-1] == args.cls
                or n.rsplit(".", 1)[-1] == args.cls]
        if args.like:
            hits = [h for h in hits if args.like in h]
        print(f"\nclasses named {args.cls}: {len(hits)}")
        for h in hits[:args.limit]:
            print("   ", h)
        return 0

    if args.member:
        found = []
        for fqn, info in jar.items():
            if args.owner:
                short = fqn.rsplit(".", 1)[-1]
                if args.owner not in (fqn, short) and not fqn.endswith("." + args.owner):
                    continue
            if args.fields:
                if args.member in info["by_desc"]["fields"]:
                    found.append((fqn, args.member,
                                  info["by_desc"]["fields"][args.member]))
            else:
                for desc, name in info["by_desc"]["methods"]:
                    if name == args.member:
                        found.append((fqn, name, desc))
        print(f"\nmembers named {args.member}: {len(found)}")
        for fqn, name, desc in found[:args.limit]:
            print(f"   {fqn}.{name}  {desc}")
        return 0

    if args.match:
        print("\nscanning all members (this is slow)")
        n = 0
        for fqn, info in sorted(jar.items()):
            for desc, name in info["by_desc"]["methods"]:
                if args.match.lower() in name.lower():
                    print(f"   {fqn}.{name}  {desc}")
                    n += 1
                    if n >= args.limit:
                        return 0
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
