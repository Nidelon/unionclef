# AGENTS.md

Context for an AI agent working in this repository. Read it before touching code.

## What this repository is

UnionClef, a Fabric mod that plays Minecraft: a pathfinder (tungsten) plus a
task layer (altoclef) driven over Py4j and MCP.

This is a **personal fork pinned to Minecraft 26.2 / Java 25**. It is not a
multi-version project any more: 1.21.x support was dropped when the tree moved
to official Mojang names, because 26.x ships unobfuscated and yarn does not
exist for it.

## Layout

| path | what lives there |
|---|---|
| `src/main/java/adris/` | altoclef, the task layer |
| `src/main/java/kaptainwutax/` | tungsten, the pathfinder |
| `src/main/resources/` | `fabric.mod.json`, mixin configs, assets |
| `tungsten/` | tungsten's own build, packaged as a separate mod |
| `versions/26.2/` | the version subproject; sources come from the repo root |
| `build.gradle` | shared build applied to the version subproject |
| `root.gradle.kts` | plugin versions, repositories, root task delegation |
| `baritone/`, `shredder/` | source references only, not compiled |

## Build

```bash
./gradlew :26.2:build
```

Needs JDK 25. The artifact lands in `versions/26.2/build/libs/`.

Run the client headless for a smoke test:

```bash
./gradlew :26.2:runClient
```

## Rules that will bite you

- **No yarn, no intermediary, no preprocessor.** The sources are already
  mojmap. Do not reintroduce `com.replaymod.preprocess` or per-version mapping
  tables: they cannot describe 26.x and the plugin no longer resolves.
- **Loom is applied as `net.fabricmc.fabric-loom`, not `fabric-loom`.** The
  short id resolves to `LoomGradlePlugin`, which demands a mappings dependency
  and fails on an unobfuscated version. The long id is
  `LoomNoRemapGradlePlugin`, which is what 26.x needs.
- **There is no `modImplementation`, no `remapJar`, no `include`.** The no-remap
  variant does not provide them. Use plain `implementation`; the shadow jar is
  the artifact.
- **Version subprojects do not own their sources.** `versions/26.2` is a build
  shell; `build.gradle` points its source sets at the repository root. If you
  add a source directory, add it there.
- **Mixin targets are strings.** `javac` never checks them. After renaming a
  method or a field, grep the mixin configs and every `@Inject`/`@Shadow`
  signature for the old name.

## Verifying a change

Compiling is not verification. The mod exposes two interfaces once a world is
loaded:

- Py4j gateway on port `25333`
- MCP server on port `25350`, token in `run/altoclef/altoclef_settings.json`

`tools/list` should return the tool set and `getGameState` should return the
bot's position and inventory. If either is empty, the mod did not initialise.

## Known open issue

Navigation does not move the bot. `MixinClientPlayerEntity.start` returns on
its first line because `TungstenMod.runKeyBinding` is null, so the whole
movement stack never ticks. Key binding registration itself looks correct, so
the cause is upstream of the tick handler.
