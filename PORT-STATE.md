# Port state: Minecraft 26.2

This fork is pinned to **Minecraft 26.2 / Java 25 / Fabric**. The 1.21.x
versions were dropped: 26.x ships unobfuscated, so the source tree is mojmap
and the old yarn-era machinery has no meaning here.

## What changed to get here

Minecraft 26.x has no yarn and no intermediary. The tree was renamed
`yarn -> intermediary -> official -> mojmap` and then hand-migrated, because a
mapping table cannot express an API that was rewritten rather than renamed:

- removed classes: `TieredItem`, `ArmorItem`, `Tiers`, `GuiGraphics`,
  `FastColor`, `Tuple`
- relocated: `ARGB`, `FuelValues`
- changed signatures: `interact` now takes an `EntityHitResult`,
  `Entity.getYaw()` became `getYRot(float)`
- rewritten subsystems: recipes (`Recipe.getResult` is gone, output comes from
  `Recipe.display()`), which is why `RecipeCompat` exists

## Build

```bash
./gradlew :26.2:build
```

Artifact: `versions/26.2/build/libs/unionclef-26.2-0.95.58.jar`

Two things about this build are not obvious and cost a day to find:

1. Loom must be applied as `net.fabricmc.fabric-loom`. The short id
   `fabric-loom` resolves to `LoomGradlePlugin`, which insists on a mappings
   dependency and dies with `Configuration 'mappings' has no dependencies` on an
   unobfuscated version. The long id is `LoomNoRemapGradlePlugin`.
2. The no-remap variant has no `modImplementation`, no `remapJar` and no
   `include`. Dependencies are plain `implementation`, and the shadow jar is the
   artifact.

## Verified

- clean build, 0 compile errors
- jar contains 700 classes, `fabric.mod.json` with both entrypoints, mixin
  configs, nested nether-pathfinder
- client starts, mixins apply, initialisation completes: Py4j on 25333, MCP on
  25350
- `tools/list` returns the tool set, `getGameState` returns live bot state

## Open

Navigation does not move the bot. `MixinClientPlayerEntity.start` returns on
its first line because `TungstenMod.runKeyBinding` is null, so the movement
stack never ticks. Registration itself looks correct, so the fault is upstream
of the tick handler.

Deliberately disabled, with reasons in the commit that touched them:
`WorldBlockModifiedMixin`, `GameOverlayMixin`, `MixinDebugRenderer`,
`MixinClientCommandSource`, `AxeItemAccessor`, `MiningToolItemAccessor`,
`DrawableHelperInvoker`, `ToolMaterialVer`. Client-side recipe enumeration is
not available in 26.2.
