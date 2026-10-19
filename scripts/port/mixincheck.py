#!/usr/bin/env python3
"""Check mixin targets against the 26.2 jar.

Mixin injection points are strings, so javac never validates them: a mod can
compile cleanly and still crash on load with "No obfuscation mapping for
@Inject method". This walks every mixin source, reads its @Mixin target and the
method names used in @Inject/@Redirect/@ModifyVariable/@Accessor, and verifies
they exist on the target class (or an ancestor) in the 26.2 jar.

Usage: mixincheck.py [--src port26/src/main/java] [--jar <26.2 client jar>]
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

MIXIN_RE = re.compile(r"@Mixin\(\s*(?:value\s*=\s*)?\{?\s*([\w.$]+)\.class")
METHOD_RE = re.compile(r'method\s*=\s*"([^"]+)"')
ACCESSOR_RE = re.compile(r"@(?:Accessor|Invoker)\(\s*(?:value\s*=\s*)?\"([^\"]+)\"")
# @Shadow members are declared inline: `@Shadow private ClientWorld world;`
SHADOW_RE = re.compile(
    r"@Shadow\s+(?:final\s+)?(?:private|protected|public)?\s*"
    r"[\w.<>\[\], ?]+?\s+(\w+)\s*(?:\(|;)")
TARGET_RE = re.compile(r'@(?:Shadow|Accessor|Invoker|Inject|Redirect|ModifyVariable|ModifyArg|ModifyArgs|WrapOperation|WrapWithCondition|ModifyExpressionValue|ModifyConstant|ModifyReturnValue)')


# Hand-verified translations for injection points the mapping tables cannot
# resolve on their own (field renames, handlers that moved, accessors that
# became accessor methods).
MANUAL = {
    ("net.minecraft.world.inventory.AbstractFurnaceMenu", "propertyDelegate"): "data",
    ("net.minecraft.client.multiplayer.MultiPlayerGameMode", "currentBreakingProgress"): "destroyProgress",
    ("net.minecraft.network.Connection", "ticks"): "tickCount",
    ("net.minecraft.client.gui.screens.DeathScreen", "message"): "causeOfDeath",
    ("net.minecraft.world.entity.Entity", "inNetherPortal"): "portalProcess",
    ("net.minecraft.client.Minecraft", "session"): "user",
    ("net.minecraft.client.Minecraft", "setScreen"): "setScreenAndShow",
    ("net.minecraft.client.Minecraft", "update"): "tick",
    ("net.minecraft.client.gui.Gui", "render"): "extractRenderState",
    ("net.minecraft.client.gui.Gui", "setOverlayMessage"): "setOverlay",
    ("net.minecraft.client.multiplayer.ClientPacketListener", "onEntityTrackerUpdate"): "handleSetEntityData",
    ("net.minecraft.client.multiplayer.ClientPacketListener", "onEntityDamage"): "handleDamageEvent",
    ("net.minecraft.client.multiplayer.ClientPacketListener", "onEntityAnimation"): "handleAnimate",
    ("net.minecraft.client.multiplayer.ClientPacketListener", "onScreenHandlerSlotUpdate"): "handleContainerSetSlot",
    ("net.minecraft.client.multiplayer.ClientPacketListener", "onInventory"): "handleContainerContent",
    ("net.minecraft.client.multiplayer.ClientPacketListener", "onPlayerPositionLook"): "handleMovePlayer",
    ("net.minecraft.client.player.LocalPlayer", "tickMovement"): "tick",
    ("net.minecraft.client.player.LocalPlayer", "getPitch"): "getXRot",
    ("net.minecraft.client.player.LocalPlayer", "getYaw"): "getYRot",
    ("net.minecraft.server.level.ServerPlayer", "damage"): "hurtServer",
    ("net.minecraft.world.level.Level", "onBlockStateChanged"): "sendBlockUpdated",
    ("net.minecraft.world.level.Level", "onBlockChanged"): "blockEntityChanged",
    ("net.minecraft.client.multiplayer.ClientSuggestionProvider", "getCompletions"): "getSuggestionsFromServer",
    ("net.minecraft.client.Minecraft", "world"): "level",
    ("net.minecraft.client.multiplayer.ClientPacketListener", "world"): "level",
    ("net.minecraft.world.entity.Entity", "yaw"): "yRot",
    ("net.minecraft.world.entity.Entity", "pitch"): "xRot",
    ("net.minecraft.world.level.chunk.LevelChunk", "getWorld"): "getLevel",
    ("net.minecraft.client.MouseHandler", "cursorDeltaX"): "accumulatedDX",
    ("net.minecraft.client.MouseHandler", "cursorDeltaY"): "accumulatedDY",
    ("net.minecraft.client.gui.components.CommandSuggestions", "completingSuggestions"): "keepSuggestions",
    ("net.minecraft.client.gui.components.CommandSuggestions", "window"): "suggestions",
    ("net.minecraft.client.gui.components.CommandSuggestions$SuggestionsList", "selection"): "current",
    ("net.minecraft.client.multiplayer.MultiPlayerGameMode", "currentBreakingPos"): "destroyBlockPos",
    ("net.minecraft.client.multiplayer.MultiPlayerGameMode", "blockBreakingCooldown"): "destroyDelay",
    ("net.minecraft.client.gui.components.CommandSuggestions", "parse"): "currentParse",
    ("net.minecraft.client.gui.components.CommandSuggestions", "x"): "commandUsagePosition",
    ("net.minecraft.client.gui.components.CommandSuggestions", "width"): "commandUsageWidth",
}


# Shadowed members are used bare inside the mixin body, so the rename has to
# cover the whole file (imports excluded).
FILE_RENAMES = {
    "CameraMixin.java": {"setPos": "setPosition"},
    "MixinChatInputSuggestor.java": {"getStartOfCurrentWord": "getLastWordIndex",
                                     "showCommandSuggestions": "updateUsageInfo",
                                     "show": "showSuggestions"},
    "MixinClientPlayNetworkHandler.java": {"sendChatMessage": "sendChat"},
    "MixinWorldChunk.java": {"getWorld": "getLevel"},
    "ClientPlayNetworkHandlerMixin.java": {"world": "level"},
    "MouseMixin.java": {"client": "minecraft"},
    "ClientBlockBreakMixin.java": {"blockBreakingCooldown": "destroyDelay",
                                   "currentBreakingPos": "destroyBlockPos",
                                   "breakingBlock": "isDestroying",
                                   "currentBreakingProgress": "destroyProgress"},
}


# Injection callbacks whose parameter list has to change to match the 26.2
# target. Kept as whole-signature swaps so the body stays untouched.
SIGNATURE_FIXES = {
    "MixinMouse.java": [
        ("injectSyntheticDeltas(CallbackInfo ci)",
         "injectSyntheticDeltas(double delta, CallbackInfo ci)"),
    ],
    "MixinInGameHud.java": [
        ("onRenderFrame(GuiGraphicsExtractor context, DeltaTracker tickCounter, CallbackInfo ci)",
         "onRenderFrame(DeltaTracker tickCounter, boolean first, boolean second, CallbackInfo ci)"),
    ],
    "ServerPlayerEntityMixin.java": [
        ("onDamage(DamageSource source, float amount, CallbackInfoReturnable<Boolean> cir)",
         "onDamage(net.minecraft.server.level.ServerLevel level, DamageSource source, float amount, CallbackInfoReturnable<Boolean> cir)"),
    ],
    "ClientUIMixin.java": [
        ("clientRender(GuiGraphicsExtractor context, DeltaTracker tickCounter, CallbackInfo ci)",
         "clientRender(DeltaTracker tickCounter, boolean first, boolean second, CallbackInfo ci)"),
    ],
    "LoadChunkMixin.java": [
        ("onLoadChunk(int x, int z, FriendlyByteBuf buf, CompoundTag nbt,",
         "onLoadChunk(int x, int z, FriendlyByteBuf buf, java.util.Map nbt,"),
    ],
    "MouseMixin.java": [
        ("onUpdateMouseHead(CallbackInfo ci)", "onUpdateMouseHead(double delta, CallbackInfo ci)"),
    ],
}


def apply_signature_fixes(root):
    hits = 0
    for name, pairs in SIGNATURE_FIXES.items():
        for path in root.rglob(name):
            text = path.read_text(encoding="utf-8")
            original = text
            for old, new in pairs:
                text = text.replace(old, new)
            if text != original:
                path.write_text(text, encoding="utf-8")
                hits += 1
    return hits


def apply_file_renames(root):
    hits = 0
    for name, mapping in FILE_RENAMES.items():
        for path in root.rglob(name):
            lines = path.read_text(encoding="utf-8").split("\n")
            out = []
            for line in lines:
                if line.lstrip().startswith("import "):
                    out.append(line)
                    continue
                for old, new in mapping.items():
                    line = re.sub(rf"\b{re.escape(old)}\b", new, line)
                out.append(line)
            new_text = "\n".join(out)
            if new_text != "\n".join(lines):
                path.write_text(new_text, encoding="utf-8")
                hits += 1
    return hits


def load_jar(path):
    spec = importlib.util.spec_from_file_location("vm", HERE / "maps" / "build_vermap.py")
    vm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vm)
    return vm.read_jar_members(Path(path))


def member_names(info, want_methods):
    if not info:
        return set()
    if want_methods:
        return {name for _, name in info["by_desc"]["methods"]}
    return set(info["by_desc"]["fields"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(REPO / "port26/src/main/java"))
    ap.add_argument("--jar", default=str(Path.home() /
                    ".gradle/caches/fabric-loom/26.2/minecraft-client.jar"))
    ap.add_argument("--hierarchy", default=str(HERE / "maps" / "hierarchy-26.2.json"))
    ap.add_argument("--fix", action="store_true",
                    help="rewrite the injection-point strings that have a unique 26.2 name")
    args = ap.parse_args()

    jar = load_jar(args.jar)
    hierarchy = json.loads(Path(args.hierarchy).read_text(encoding="utf-8"))

    def visible(cls, want_methods):
        out, seen, queue = set(), set(), [cls]
        while queue:
            c = queue.pop(0)
            if c in seen:
                continue
            seen.add(c)
            out |= member_names(jar.get(c), want_methods)
            queue.extend(hierarchy.get(c, []))
        return out

    # yarn -> mojmap tables, used to translate the injection-point strings
    sys.path.insert(0, str(HERE / "maps"))
    import fix_members as fm
    tables = {}
    for tag, comp in (("adris", HERE / "maps/1.21.1/composed.json"),
                      ("kaptainwutax", HERE / "maps/1.21.11/composed.json")):
        classes, members, rev, simple, gi = fm.load_maps(str(comp))
        tables[tag] = (classes, members, rev)

    def suggest(target, yarn_name, tag):
        """Translate a yarn method name to the 26.2 name, if unambiguous."""
        classes, members, rev = tables[tag]
        yarn_cls = rev.get(target)
        if not yarn_cls:
            return None
        cands = members.get(f"{yarn_cls}#{yarn_name}") or []
        alive = [c for c in cands if c in visible(target, True)]
        return alive[0] if len(alive) == 1 else None

    # injection callbacks must take the target's parameters plus CallbackInfo
    INJECT_SIG_RE = re.compile(
        r"@Inject\(((?:[^()]|\([^()]*\))*)\)\s*"
        r"(?:@[\w.]+(?:\([^)]*\))?\s*)*"
        r"(?:public|private|protected)?\s*[\w.<>\[\]]+\s+\w+\s*\(([^)]*)\)", re.S)
    INJECT_NAME_RE = re.compile(r'method\s*=\s*"([^"(]+)')

    def param_count(params):
        params = params.strip()
        if not params:
            return 0
        depth, count = 0, 1
        for ch in params:
            if ch in "(<[{":
                depth += 1
            elif ch in ")>]}":
                depth -= 1
            elif ch == "," and depth == 0:
                count += 1
        return count

    def count_desc_params(args):
        """Count parameters in a JVM descriptor argument list."""
        n, i = 0, 0
        while i < len(args):
            c = args[i]
            if c == "[":
                i += 1
                continue
            if c == "L":
                i = args.index(";", i) + 1
                n += 1
                continue
            i += 1
            n += 1
        return n

    def target_arities(cls, name):
        info = jar.get(cls)
        if not info:
            return set()
        out = set()
        for desc, m in info["by_desc"]["methods"]:
            if m != name:
                continue
            args = desc[1:desc.index(")")] if desc.startswith("(") else ""
            out.add(count_desc_params(args))
        return out

    problems = []
    checked = 0
    for path in sorted(Path(args.src).rglob("*.java")):
        text = path.read_text(encoding="utf-8")
        if "@Mixin" not in text:
            continue
        # strip comments: annotations quoted in prose are not real targets
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"//[^\n]*", "", text)
        m = MIXIN_RE.search(text)
        if not m:
            continue
        target = m.group(1)
        if "." not in target:
            # mixins name their target by simple name; resolve it through the
            # file's imports, then fall back to a unique jar match
            by_simple = {simple: f"{pkg}.{simple}"
                         for pkg, simple in re.findall(
                             r"^import\s+([\w.]+)\.(\w+);", text, re.M)}
            if target in by_simple:
                target = by_simple[target]
            else:
                cands = [c for c in jar if c.rsplit(".", 1)[-1] == target]
                if len(cands) == 1:
                    target = cands[0]
        if target not in jar and "." in target:
            # nested mixin targets are written Outer.Inner but stored as Outer$Inner
            head, _, tail = target.rpartition(".")
            if f"{head}${tail}" in jar:
                target = f"{head}${tail}"
        if target not in jar:
            problems.append((path.name, target, "<target class missing in 26.2>", None))
            continue
        methods = visible(target, True)
        fields = visible(target, False)
        for name in METHOD_RE.findall(text):
            checked += 1
            base = name.split("(")[0].strip()
            if base in ("<init>", "<clinit>"):
                continue
            if base not in methods:
                tag = "kaptainwutax" if "kaptainwutax" in str(path) else "adris"
                fix = MANUAL.get((target, base)) or suggest(target, base, tag)
                problems.append((path.name, target, f"method {base}", fix))
        for ann, params in INJECT_SIG_RE.findall(text):
            nm = INJECT_NAME_RE.search(ann)
            if not nm:
                continue
            checked += 1
            base = nm.group(1).strip()
            arities = target_arities(target, base)
            if not arities:
                continue
            want = param_count(params) - 1  # minus CallbackInfo
            if want not in arities:
                problems.append((path.name, target,
                                 f"signature {base}({want} args, target has {sorted(arities)})",
                                 None))
        for name in SHADOW_RE.findall(text):
            checked += 1
            if name in methods or name in fields:
                continue
            tag = "kaptainwutax" if "kaptainwutax" in str(path) else "adris"
            fix = MANUAL.get((target, name)) or suggest(target, name, tag)
            problems.append((path.name, target, f"shadow {name}", fix))
        for name in ACCESSOR_RE.findall(text):
            checked += 1
            base = name.split("(")[0].strip()
            if base not in methods and base not in fields:
                tag = "kaptainwutax" if "kaptainwutax" in str(path) else "adris"
                fix = MANUAL.get((target, base)) or suggest(target, base, tag)
                problems.append((path.name, target, f"accessor {base}", fix))

    print(f"mixin files checked : {len({p[0] for p in problems}) + 0}")
    print(f"references checked  : {checked}")
    print(f"problems            : {len(problems)}")
    if args.fix:
        sigs = apply_signature_fixes(Path(args.src))
        if sigs:
            print(f"signatures fixed    : {sigs}")
        renamed = apply_file_renames(Path(args.src))
        if renamed:
            print(f"files renamed       : {renamed}")
        applied = 0
        for path in sorted(Path(args.src).rglob("*.java")):
            text = path.read_text(encoding="utf-8")
            original = text
            for f, tgt, what, fix in problems:
                if f != path.name or not fix:
                    continue
                kind, old = what.split(" ", 1)
                if kind == "shadow":
                    # rename only the declaration and `this.` accesses: a blanket
                    # rename also hits imports and unrelated method calls
                    text = re.sub(
                        rf"(@Shadow\s+(?:(?:private|protected|public|final)\s+)*"
                        rf"[\w.<>\[\], ?]*?\s*){re.escape(old)}(\s*;)",
                        rf"\g<1>{fix}\g<2>", text)
                    text = re.sub(rf"\bthis\.{re.escape(old)}\b",
                                  f"this.{fix}", text)
                    continue
                text = re.sub(rf'(method\s*=\s*"){re.escape(old)}(?=[("])',
                              rf"\g<1>{fix}", text)
                text = re.sub(rf'(@(?:Accessor|Invoker)\(\s*(?:value\s*=\s*)?"){re.escape(old)}(")',
                              rf"\g<1>{fix}\g<2>", text)
            if text != original:
                path.write_text(text, encoding="utf-8")
                applied += 1
        print(f"files rewritten     : {applied}")

    fixable = 0
    for f, t, what, fix in problems:
        if fix:
            fixable += 1
            print(f"  {f}: {what} on {t}  ->  {fix}")
        else:
            print(f"  {f}: {what} on {t}")
    print(f"auto-fixable        : {fixable}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
