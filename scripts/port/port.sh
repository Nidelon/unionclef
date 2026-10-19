#!/usr/bin/env bash
# Regenerate src26/ from src/.
#
# The tree holds two mods with DIFFERENT base Minecraft versions, so each subtree
# gets its own preprocessor target and its own yarn -> mojmap table:
#
#   src/main/java/adris/**        1.21.1  (its MC >= 12111 branches are unfinished WIP)
#   tungsten/src/main/java/kaptainwutax/** 1.21.11 (its MC < 12111 branches are the fallback)
#
# Both are ported to Minecraft 26.2 / Java 25, which is why the preprocessor is
# pinned to each SOURCE version rather than to the port target: the WIP 1.21.11
# branches of adris never compiled, so the port builds on the 1.21.1 baseline
# that does.
#
# src26/ is derived: never edit it by hand (except through the member-rename
# loop), rerun this script instead.
set -euo pipefail
cd "$(dirname "$0")/../.."

MAPS=scripts/port/maps

echo "== preprocess adris (base 1.21.1) =="
python3 scripts/port/preprocess.py src/main/java/adris port26/src/main/java/adris --mc 12101
python3 scripts/port/preprocess.py src/main/java/adris port26/src/main/java/adris --mc 12111 --in-place \
    --only altoclef/util/helpers/ItemHelper.java \
    --only altoclef/util/helpers/StorageHelper.java \
    --only altoclef/tasks/misc/EquipArmorTask.java \

# these three are further along on their own 1.21.11 branch: the 1.21.1 side
# still uses classes 26.2 deleted (TieredItem, ArmorItem, offHand, getArmorStack)
python3 scripts/port/preprocess.py src/main/java/adris port26/src/main/java/adris --mc 12111 --in-place \
    --only altoclef/util/helpers/ItemHelper.java \
    --only altoclef/util/helpers/StorageHelper.java \
    --only altoclef/tasks/misc/EquipArmorTask.java \

echo
echo "== preprocess kaptainwutax (base 1.21.11) =="
python3 scripts/port/preprocess.py tungsten/src/main/java/kaptainwutax port26/src/main/java/kaptainwutax --mc 12111

echo
echo "== drop files that the port no longer needs =="
# ToolMaterialVer only served the deleted Tier/Tiers API; nothing references it
rm -f port26/src/main/java/adris/altoclef/multiversion/ToolMaterialVer.java
sed -i '/import adris.altoclef.multiversion.ToolMaterialVer;/d' \
    port26/src/main/java/adris/altoclef/util/helpers/StorageHelper.java
echo "removed ToolMaterialVer"
# mixins that target classes 26.2 deleted, plus the debug path renderer whose
# whole render API changed; none of them carry gameplay logic
rm -f port26/src/main/java/adris/altoclef/mixins/AxeItemAccessor.java \
      port26/src/main/java/adris/altoclef/mixins/DrawableHelperInvoker.java \
      port26/src/main/java/adris/altoclef/mixins/GameOverlayMixin.java \
      port26/src/main/java/adris/altoclef/mixins/WorldBlockModifiedMixin.java \
      port26/src/main/java/kaptainwutax/tungsten/mixin/MixinClientCommandSource.java \
      port26/src/main/java/adris/altoclef/mixins/MiningToolItemAccessor.java \
      port26/src/main/java/kaptainwutax/tungsten/mixin/MixinDebugRenderer.java
echo "removed dead mixins"

echo
echo "== resources =="
rm -rf port26/src/main/resources
mkdir -p port26/src/main/resources
# the port ships ONE jar, so both mods' resources are merged here; tungsten's
# own fabric.mod.json is skipped because its entrypoint is added to altoclef's
cp -r src/main/resources/. port26/src/main/resources/
cp -r tungsten/src/main/resources/assets/. port26/src/main/resources/assets/
cp tungsten/src/main/resources/tungsten.mixins.json port26/src/main/resources/
echo "merged altoclef + tungsten resources"

echo
# the mixin configs only exist after the resources copy, so prune them here
python3 - <<'PY'
import json, pathlib
for name, dead in (("altoclef.mixins.json", ["AxeItemAccessor", "MiningToolItemAccessor", "DrawableHelperInvoker", "GameOverlayMixin", "WorldBlockModifiedMixin"]),
                   ("tungsten.mixins.json", ["MixinDebugRenderer", "MixinClientCommandSource"])):
    p = pathlib.Path("port26/src/main/resources") / name
    if not p.exists():
        continue
    data = json.loads(p.read_text())
    for key in ("mixins", "client", "server"):
        if key in data:
            data[key] = [m for m in data[key] if m not in dead]
    p.write_text(json.dumps(data, indent=2) + "\n")
PY

echo "== rename adris: yarn 1.21.1 -> mojmap =="
python3 scripts/port/maps/apply_map.py port26/src/main/java/adris --map "$MAPS/1.21.1/maps.json"

echo
echo "== rename kaptainwutax: yarn 1.21.11 -> mojmap =="
python3 scripts/port/maps/apply_map.py port26/src/main/java/kaptainwutax --map "$MAPS/1.21.11/maps.json"

echo
echo "== deterministic fixups (removed classes, renamed getters) =="
python3 scripts/port/fixups.py port26/src/main/java

# second pass: a few nested-class references only become resolvable once the
# first pass has rewritten their imports
echo
echo "== second rename pass (nested classes) =="
python3 scripts/port/maps/apply_map.py port26/src/main/java/adris --map "$MAPS/1.21.1/maps.json" >/dev/null
python3 scripts/port/maps/apply_map.py port26/src/main/java/kaptainwutax --map "$MAPS/1.21.11/maps.json" >/dev/null
echo "done"

echo
echo "== adris: mojmap 1.21.1 -> mojmap 26.2 (moves and renames) =="
python3 scripts/port/maps/apply_map.py port26/src/main/java/adris --map "$MAPS/1.21.1/vermap.json"

echo
echo "== kaptainwutax: mojmap 1.21.11 -> mojmap 26.2 (moves and renames) =="
python3 scripts/port/maps/apply_map.py port26/src/main/java/kaptainwutax --map "$MAPS/1.21.11/vermap.json"

echo
echo "== mixin injection points (strings javac cannot check) =="
python3 scripts/port/mixincheck.py --fix | tail -3 || true
