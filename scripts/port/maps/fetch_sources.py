#!/usr/bin/env python3
"""Download the mapping sources for one Minecraft version.

Usage: fetch_sources.py <mc-version> <yarn-build>

Downloads into scripts/port/maps/<mc-version>/:
  yarn.jar     tiny v2, intermediary -> yarn named
  inter.jar    tiny v2, official -> intermediary
  client.txt   Mojang proguard mappings, mojmap -> official
  client.jar   the obfuscated client jar (used for the class hierarchy)

Both the obfuscated client jar and the merged-jar intermediary are needed: the
official member names in Mojang's client mappings and in Fabric's intermediary
diverge for some members, and having the client jar lets the hierarchy be read
straight from bytecode.
"""
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
FABRIC = "https://maven.fabricmc.net/net/fabricmc"
MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached  {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    print(f"  getting {dest.name} <- {url}")
    urllib.request.urlretrieve(url, dest)
    print(f"  saved   {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    mc, yarn_build = sys.argv[1], sys.argv[2]
    out = HERE / mc
    out.mkdir(parents=True, exist_ok=True)

    fetch(f"{FABRIC}/yarn/{yarn_build}/yarn-{yarn_build}-v2.jar", out / "yarn.jar")
    fetch(f"{FABRIC}/intermediary/{mc}/intermediary-{mc}-v2.jar", out / "inter.jar")

    manifest = json.load(urllib.request.urlopen(MANIFEST, timeout=60))
    entry = next((v for v in manifest["versions"] if v["id"] == mc), None)
    if entry is None:
        print(f"version {mc} not in the Mojang manifest", file=sys.stderr)
        return 1
    meta = json.load(urllib.request.urlopen(entry["url"], timeout=60))
    fetch(meta["downloads"]["client_mappings"]["url"], out / "client.txt")
    fetch(meta["downloads"]["client"]["url"], out / "client.jar")

    print(f"\nready: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
