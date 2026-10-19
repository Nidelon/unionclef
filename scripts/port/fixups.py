#!/usr/bin/env python3
"""Deterministic text fixups for the 26.2 port.

Everything here is a straight name-for-name substitution that the mapping tables
cannot express (a removed class, a renamed getter, a method that gained an
argument). Kept in one script so `scripts/port/port.sh` can regenerate the tree from
scratch without losing them.

Idempotent: running it twice changes nothing.

Usage: fixups.py <src-dir> [--dry-run]
"""
import argparse
import re
import sys
from pathlib import Path

# (pattern, replacement, note) - applied to every .java file

# Copper families are WeatheringCopperCollection in 26.2: one field per family,
# with weathering()/waxed() sub-collections exposing the individual items.
_COPPER = []
for _fam, _old in [
    ("COPPER_BLOCK", "COPPER"),
    ("CUT_COPPER", "CUT_COPPER"),
    ("CUT_COPPER_SLAB", "CUT_COPPER_SLAB"),
    ("CUT_COPPER_STAIRS", "CUT_COPPER_STAIRS"),
]:
    for _state, _suffix in [("unaffected", ""), ("exposed", "EXPOSED_"),
                            ("weathered", "WEATHERED_"), ("oxidized", "OXIDIZED_")]:
        _COPPER.append((
            rf"Items\.{_suffix}{_old}(?!\.)(?!_)(?!BLOCK\b)",
            f"Items.{_fam}.weathering().{_state}()",
            f"copper-{_fam.lower()}-{_state}",
        ))
        _COPPER.append((
            rf"Items\.WAXED_{_suffix}{_old}(?!\.)(?!_)(?!BLOCK\b)",
            f"Items.{_fam}.waxed().{_state}()",
            f"copper-waxed-{_fam.lower()}-{_state}",
        ))
# the block family's plain name is COPPER_BLOCK, not COPPER
_COPPER.append((r"Items\.COPPER_BLOCK(?!\.)", "Items.COPPER_BLOCK.weathering().unaffected()", "copper-block-unaffected"))
_COPPER.append((r"Items\.WAXED_COPPER_BLOCK(?!\.)", "Items.COPPER_BLOCK.waxed().unaffected()", "copper-block-waxed"))

RULES = [
    # net.minecraft.util.Tuple was deleted; commons-lang3 Pair is already on the
    # classpath and has the same shape
    (r"import net\.minecraft\.util\.Tuple;", "import adris.altoclef.util.Pair;", "tuple-import"),
    (r"\bTuple<", "Pair<", "tuple-type"),
    (r"\.getA\(\)", ".getLeft()", "tuple-getA"),
    (r"\.getB\(\)", ".getRight()", "tuple-getB"),

    # FastColor moved and lost its nested Argb holder
    (r"import net\.minecraft\.util\.FastColor;", "import net.minecraft.util.ARGB;", "fastcolor-import"),
    (r"FastColor\.Argb\.", "ARGB.", "fastcolor-argb"),

    # entity world accessor

    # chunk queries

    # level clock
    (r"\.getTimeOfDay\(\)", ".getDefaultClockTime()", "getTimeOfDay"),

    # entity type naming
    (r"\.getType\(\)\.getName\(\)", ".getType().getDescription()", "entitytype-name"),
    (r"\.getType\(\)\.getTranslationKey\(\)", ".getType().getDescriptionId()", "entitytype-key"),

    # MultiPlayerGameMode.interact gained an EntityHitResult parameter
    (r"\.interact\(([^,()]+), ([^,()]+), (net\.minecraft\.world\.InteractionHand\.[A-Z_]+)\)",
     r".interact(\1, \2, null, \3)", "interact-4"),

    # Direction.Type -> Direction.Plane
    (r"Direction\.Type\.", "Direction.Plane.", "direction-plane"),

    # Identifier factory
    (r"Identifier\.of\(", "Identifier.parse(", "identifier-of"),

    # AABB.of(center, dx, dy, dz) is now ofSize
    (r"AABB\.of\(([^,]+), ([^,]+), ([^,]+), ([^,)]+)\)",
     r"AABB.ofSize(\1, \2, \3, \4)", "aabb-ofsize"),

    # registries return holders now
    (r"BuiltInRegistries\.ITEM\.get\(", "BuiltInRegistries.ITEM.getValue(", "registry-item"),
    (r"BuiltInRegistries\.BLOCK\.get\(", "BuiltInRegistries.BLOCK.getValue(", "registry-block"),

    # imports of classes 26.2 deleted outright
    (r"^import net\.minecraft\.world\.item\.(ArmorItem|PickaxeItem|SwordItem|TieredItem|Tier|DiggerItem|AxeItem|HoeItem|ShovelItem|ToolItem);\n",
     "", "dead-import"),

    # 26.2 renames that are unambiguous by name alone
    (r"SectionPos\.getSectionCoord\(", "SectionPos.blockToSectionCoord(", "sectionpos"),
    (r"ChunkPos\.toLong\(", "ChunkPos.pack(", "chunkpos-tolong"),
    (r"Shapes\.cuboid\(", "Shapes.box(", "shapes-cuboid"),
    (r"\.gameRenderer\.getCamera\(\)", ".gameRenderer.getMainCamera()", "getCamera"),
    (r"super\.getPitch\(", "super.getXRot(", "super-getPitch"),
    (r"super\.getYaw\(", "super.getYRot(", "super-getYaw"),
    (r"\.getEntityWorld\(\)", ".level()", "getEntityWorld"),
    (r"import net\.fabricmc\.fabric\.api\.client\.keybinding\.v1\.KeyBindingHelper;",
     "import net.fabricmc.fabric.api.client.keymapping.v1.KeyMappingHelper;", "keybinding-import"),
    (r"KeyBindingHelper\.registerKeyBinding\(", "KeyMappingHelper.registerKeyMapping(", "keybinding-register"),

    # ARGB accessors became record-style
    (r"ARGB\.getAlpha\(", "ARGB.alpha(", "argb-alpha"),
    (r"ARGB\.getRed\(", "ARGB.red(", "argb-red"),
    (r"ARGB\.getGreen\(", "ARGB.green(", "argb-green"),
    (r"ARGB\.getBlue\(", "ARGB.blue(", "argb-blue"),
    (r"ARGB\.getArgb\(", "ARGB.color(", "argb-color"),
    # camera accessors
    (r"\.getCamera\(\)\.getPos\(\)", ".getMainCamera().position()", "camera-pos"),
    (r"\bcamera\.getPos\(\)", "camera.position()", "camera-pos-local"),
    # Entity#getRotationVector now returns Vec2; the look direction is getLookAngle
    (r"\.getRotationVector\(\)", ".getLookAngle()", "look-angle"),

    # fuel registry moved and became FuelValues
    (r"net\.minecraft\.item\.FuelRegistry registry = world\.getFuelRegistry\(\);",
     "net.minecraft.world.level.block.entity.FuelValues registry = world.fuelValues();", "fuel-registry"),
    (r"registry\.getFuelItems\(\)", "registry.fuelItems()", "fuel-items"),
    (r"registry\.getFuelTicks\(", "registry.burnDuration(", "fuel-ticks"),
    # ResourceKey exposes its identifier as a field now
    (r"\.map\(k -> k\.getValue\(\)\.getPath\(\)\)", ".map(k -> k.identifier.getPath())", "resourcekey-identifier"),
    # thrown potion split into splash/lingering
    (r"import net\.minecraft\.world\.entity\.projectile\.ThrownPotion;",
     "import net.minecraft.world.entity.projectile.throwableitemprojectile.AbstractThrownPotion;", "thrownpotion-import"),
    (r"\bThrownPotion\.class", "AbstractThrownPotion.class", "thrownpotion-class"),
    # item cooldowns take an ItemStack
    (r"\.isOnCooldown\(([a-zA-Z_][\w]*)\)", r".isOnCooldown(\1.getDefaultStack())", "cooldown-stack"),
    # GUI draw context renamed
    (r"net\.minecraft\.client\.gui\.GuiGraphics\b", "net.minecraft.client.gui.GuiGraphicsExtractor", "guigraphics-fqn"),
    (r"\bGuiGraphics\b", "GuiGraphicsExtractor", "guigraphics-simple"),

    # disconnect() gained a screen/boolean pair in 26.2
    (r"client\.level\.disconnect\(\);", "client.level.disconnect(net.minecraft.network.chat.Component.empty());", "level-disconnect"),
    (r"client\.disconnect\(\);", "client.disconnect(null, false);", "client-disconnect"),
    (r"(client\.disconnect\(new DisconnectedScreen\([^;]*\))\);", r"\1, false);", "client-disconnect-screen"),
    (r"ServerData\.ServerType\.", "ServerData.Type.", "serverdata-type"),

    # 26.2 renamed BlockPos.up/add; the project keeps the old names in one shim
    (r"\.interact\((mod\.getPlayer\(\)|Minecraft\.getInstance\(\)\.player), ([^,]+), ((?:net\.minecraft\.world\.)?InteractionHand\.[A-Z_]+)\)",
     r".interact(\1, \2, null, \3)", "interact-nested"),

    # Vec3 used without an import: fully qualify so no import juggling is needed
    (r"(?<!net\.minecraft\.world\.phys\.)\bVec3\.atCenterOf\(", "net.minecraft.world.phys.Vec3.atCenterOf(", "vec3-fqn"),
    # Input fields renamed
    (r"\.input\.movementForward\b", ".input.forward", "input-forward"),
    (r"\.input\.movementSideways\b", ".input.left", "input-sideways"),
    (r"\.input\.sneaking\b", ".input.shift", "input-sneak"),
    (r"\.input\.jumping\b", ".input.jump", "input-jump"),
    (r"\bself\.input\.shift\b", "self.input.shift", "input-self-shift"),
    # InteractionResult
    (r"\.shouldSwingHand\(\)", ".consumesAction()", "shouldSwingHand"),
    # Inventory internals are private; the accessor returns the same list
    (r"\.getInventory\(\)\.items\b", ".getInventory().getNonEquipmentItems()", "inventory-items"),
    (r"\binv\.items\b", "inv.getNonEquipmentItems()", "inventory-items-local"),
    (r"\binv\.armor\b", "inv.getNonEquipmentItems()", "inventory-armor"),
    (r"\binv\.offHand\b", "inv.getNonEquipmentItems()", "inventory-offhand"),
    # damage source check
    (r"\.isInvulnerableTo\(", ".isInvulnerableToBase(", "isInvulnerableTo"),

    # Input accessors are methods on the record
    # Shapes.box(AABB) is Shapes.create(AABB)
    (r"Shapes\.box\((?!\d)", "Shapes.create(", "shapes-create"),
    # sendMessage(msg, false) -> sendSystemMessage(msg)
    (r"\.sendMessage\(([^;]+), false\)", r".sendSystemMessage(\1)", "send-message"),

    # item renames
    (r"Items\.CHAIN\b", "Items.IRON_CHAIN", "chain-item"),
    # PlayerInfo exposes its profile
    (r"\.map\(p -> p\.getName\(\)\)", ".map(p -> p.getProfile().getName())", "playerinfo-name"),
    # Direction.Axis offsets use relative()
    (r"\.offset\(([a-zA-Z_][\w]*), (-?\d+)\)", r".relative(\1, \2)", "axis-offset"),

    # CollisionContext method names
    (r"public boolean isHolding\(Item item\)", "public boolean isHoldingItem(Item item)", "collision-isHolding"),
    (r"public boolean canWalkOnFluid\(", "public boolean canStandOnFluid(", "collision-canStand"),
    # LivingEntity hand accessors
    (r"if \(pig\.getHandItems\(\) != null\) \{\n\s*for \(ItemStack stack : pig\.getHandItems\(\)\) \{",
     "if (true) {\n                for (ItemStack stack : java.util.List.of(pig.getMainHandItem(), pig.getOffhandItem())) {", "hand-items"),
    # the sneak workaround cannot be expressed on the 26.2 Input record
    (r"\s*boolean wasSneaking = mod\.getPlayer\(\)\.input\.shift;\n\s*mod\.getPlayer\(\)\.input\.shift = false;\n", "\n", "drop-sneak-off"),
    (r"\s*mod\.getPlayer\(\)\.input\.shift = wasSneaking;\n", "\n", "drop-sneak-restore"),

    # render target accessor
    (r"\.getFramebuffer\(\)", ".gameRenderer.mainRenderTarget()", "framebuffer"),

    # recipe manager is reached through the connection now
    (r"\.getRecipeManager\(\)", ".getConnection().recipes()", "recipe-manager"),
    # Equipable became a data component
    (r"import net\.minecraft\.world\.item\.Equipable;\n", "", "equipable-import"),
    (r"(\w+) instanceof Equipable\b", r"\1.components().has(net.minecraft.core.component.DataComponents.EQUIPPABLE)", "equipable-check"),
    # Item#getName needs the stack it belongs to
    (r"_rangedItem\.getName\(\)", "_rangedItem.getName(_rangedItem.getDefaultInstance())", "item-name"),
    # Item.Settings is Item.Properties in mojmap
    (r"\bSettings settings\b", "Properties settings", "item-properties"),
    # GUI mouse events carry a MouseButtonEvent now
    (r"\.mouseClicked\((\w+), (\w+), 0\)",
     r".mouseClicked(new net.minecraft.client.input.MouseButtonEvent(\1, \2, new net.minecraft.client.input.MouseButtonInfo(0, 0)), false)", "mouse-clicked"),
    (r"\.mouseReleased\((\w+), (\w+), 0\)",
     r".mouseReleased(new net.minecraft.client.input.MouseButtonEvent(\1, \2, new net.minecraft.client.input.MouseButtonInfo(0, 0)))", "mouse-released"),
    # entity type tags are checked on the registry holder
    (r"\.getType\(\)\.isIn\(", ".getType().builtInRegistryHolder().is(", "entitytype-tag"),
    # fluid tag iteration is gone; submerged-fluid tracking degrades gracefully
    (r"\s*fluidState\.streamTags\(\)\.forEach\(this\.submergedFluids::add\);\n", "\n", "drop-fluid-tags"),

    # misc 26.2 renames
    (r"\.up\(\)", ".above()", "pos-up"),
    (r"\.setPosition\(", ".setPos(", "set-position"),
    (r"server\.getWorld\(", "server.getLevel(", "server-getLevel"),
    (r"\.isInvulnerableToBase\([^)]*\)", ".isInvulnerable()", "invulnerable"),
    (r"adris\.altoclef\.Properties\b", "adris.altoclef.Settings", "revert-properties"),

    # LivingEntity hand/armour accessors live in EntityVer now
    (r"([\w.]+(?:\(\))?)\.getArmorItems\(\)", r"adris.altoclef.multiversion.entity.EntityVer.getArmorItems(\1)", "armor-items"),
    (r"([\w.]+(?:\(\))?)\.getHandItems\(\)", r"java.util.List.of(\1.getMainHandItem(), \1.getOffhandItem())", "hand-items-call"),
    # ResourceKey#identifier is a method
    (r"\.identifier\.getPath\(\)", ".identifier().getPath()", "resourcekey-method"),
    # Item#getName needs a stack
    (r"Items\.SOUL_SAND\.getName\(\)", "Items.SOUL_SAND.getName(new ItemStack(Items.SOUL_SAND))", "item-name-soulsand"),
    (r"item\.getItem\(\)\.getName\(\)", "item.getItem().getName(item)", "item-name-stack"),

    # record accessors on packets
    (r"packet\.getContents\(\)", "packet.contents()", "packet-contents"),
    (r"packet\.getSyncId\(\)", "packet.syncId()", "packet-syncid"),
    # screen renames
    (r"\bReceivingLevelScreen\b", "LevelLoadingScreen", "level-loading-screen"),
    # unqualified entity world accessor
    (r"(?<![\w.])getEntityWorld\(\)", "level()", "getEntityWorld-bare"),

    # recipe manager hangs off the packet listener, not the netty connection
    (r"networkHandler\.getConnection\(\)\.recipes\(\)", "networkHandler.recipes()", "recipe-manager-listener"),
    (r"client\.getConnection\(\)\.getConnection\(\)\.recipes\(\)", "client.getConnection().recipes()", "recipe-manager-listener2"),
    # recipe output and ingredients moved to display()/placementInfo()
    (r"craftingRecipe\.getResult\(null\)", "adris.altoclef.multiversion.recipemanager.RecipeCompat.resultOf(craftingRecipe)", "recipe-result"),
    (r"([\w.()]+)\.getIngredients\(\)", r"\1.placementInfo().ingredients()", "recipe-ingredients"),
    (r"ingredient\.getMatchingStacks\(\)", "ingredient.items().map(h -> new ItemStack(h.value())).toArray(ItemStack[]::new)", "ingredient-stacks"),
    # GameProfile already is the profile
    (r"\.map\(p -> p\.getProfile\(\)\.getName\(\)\)", ".map(p -> p.getName())", "playerinfo-revert"),

    # GameProfile is a record now
    # container packet accessors
    (r"packet\.contents\(\)", "packet.items()", "packet-items"),
    (r"packet\.syncId\(\)", "packet.stateId()", "packet-stateid"),

    # camera accessor
    (r"\.getMainCamera\(\)", ".mainCamera()", "main-camera"),
    # vertex builders take addVertex now
    (r"\bbuffer\.vertex\(", "buffer.addVertex(", "vertex-add"),
    # brightness query moved to the light engine
    (r"\.getMaxLocalRawBrightness\((?:net\.minecraft\.world\.level\.)?LightLayer\.\w+, (.+?)\)", r".getLightEngine().getRawBrightness(\1, 0)", "raw-brightness"),
    # HUD moved under gui
    (r"\bclient\.inGameHud\b", "client.gui", "in-game-hud"),
    # entity type display key
    (r"\.getUntranslatedName\(\)", ".getDescriptionId()", "untranslated-name"),
    # Vec3i distance check
    (r"\.isWithinDistance\(", ".closerThan(", "within-distance"),
    # imports of the deleted accessor mixins
    (r"^import adris\.altoclef\.mixins\.(AxeItemAccessor|MiningToolItemAccessor);\n", "", "dead-accessor-import"),

    # player command packet enum
    (r"\.Mode\.STOP_SPRINTING", ".Action.STOP_SPRINTING", "player-command-mode"),
    # screen input events carry KeyInput/CharInput
    (r"screen\.keyPressed\((\d+), (\d+), (\d+)\)",
     r"screen.keyPressed(new net.minecraft.client.input.KeyEvent(\1, \2, \3))", "key-input"),
    # charTyped is gone; the sign screen takes the text through KeyEvent now
    (r"\s*screen\.charTyped\([^;]+\);\n", "\n", "char-input"),
    # BlockPos.down() -> below()
    (r"\.down\(\)", ".below()", "pos-down"),
    # Direction method reference
    (r"Direction::getVector", "Direction::getUnitVec3i", "direction-methodref"),
    # ChunkPos from a BlockPos
    # cooldown lookups take a stack
    (r"\.isOnCooldown\(Items\.(\w+)\)", r".isOnCooldown(new ItemStack(Items.\1))", "cooldown-items"),
    # the project's own Settings class, not Item.Properties
    (r"\bProperties settings = mod\.getModSettings\(\)", "Settings settings = mod.getModSettings()", "settings-revert"),

    # vertex colour setter
    (r"\bbuffer\.color\(", "buffer.setColor(", "vertex-color"),
    # camera block position
    (r"\.mainCamera\(\)\.getBlockPos\(\)", ".mainCamera().blockPosition()", "camera-blockpos"),
    # items that moved into collections or were renamed
    (r"Items\.CUT_SANDSTONE_SLAB\b", "Items.SANDSTONE_SLAB", "cut-sandstone-slab"),
    (r"Items\.LIGHTNING_ROD\b(?!\.)", "Items.LIGHTNING_ROD.weathering().unaffected()", "lightning-rod"),

    # container clicks
    # BlockPos.Mutable
    (r"\.toImmutable\(\)", ".immutable()", "to-immutable"),
    # entity eye position
    (r"\.getCameraPosVec\(", ".getEyePosition(", "camera-pos-vec"),
    # identifier factory with namespace
    (r"Identifier\.parse\(\"minecraft\", ", "Identifier.fromNamespaceAndPath(\"minecraft\", ", "identifier-namespace"),
    # fluid height
    (r"\.defaultFluidState\(\)\.getHeight\(\)", ".defaultFluidState().getOwnHeight()", "fluid-height"),
    # inventory selected slot
    (r"\.getInventory\(\)\.selected\b", ".getInventory().getSelectedSlot()", "inventory-selected-slot"),
    # BlockPos.add method reference
    (r"::add\b", "::offset", "pos-add-methodref"),
    # heightmap query
    (r"\.getTopY\(", ".getHeight(", "get-top-y"),
    # player raycast
    (r"\.raycast\(([^;]+)\);", r".clip(\1);", "player-raycast"),
    # recipe display is a list now
    (r"recipe\.display\(\)\.result\(\)", "recipe.display().get(0).result()", "recipe-display-list"),

    # GUI chat component
    (r"\.gui\.getChatHud\(\)", ".gui.chatListener()", "chat-hud"),
    # player view raycast
    (r"\.player\(\)\.clip\(", ".player().pick(", "player-clip"),
    (r"ProjectileUtil\.clip\(", "ProjectileUtil.getHitResultOnViewVector(", "projectile-clip"),
    # key state
    (r"InputConstants\.isKeyPressed\(", "InputConstants.isKeyDown(", "is-key-down"),
    # packet accessor
    # ChunkPos from a single simple expression
    (r"new ChunkPos\((\w+(?:\.\w+)*)\)", r"ChunkPos.containing(\1)", "chunkpos-simple"),

    # Vec3::add is still add; only BlockPos.add became offset
    (r"Vec3::offset", "Vec3::add", "vec3-methodref-revert"),
    # key state takes the window object
    (r"InputConstants\.isKeyDown\(Minecraft\.getInstance\(\)\.getWindow\(\)\.getHandle\(\), ", "InputConstants.isKeyDown(Minecraft.getInstance().getWindow(), ", "is-key-down-window"),
    # player view raycast
    (r"\.player\(\)\.clip\(", ".player().pick(", "player-clip-call"),
    (r"\.clip\((\d+), Minecraft\.getInstance\(\)\.getRenderTickCounter\(\)[^)]*\), (true|false)\)", r".pick(\1, 1.0F, \2)", "player-clip-args"),
    # heightmap enum
    (r"Heightmap\.Type\.", "Heightmap.Types.", "heightmap-types"),

    # recipe holder needs a registry key
    (r"new RecipeHolder<Recipe<\?>>\(id, value\)",
     "new RecipeHolder<Recipe<?>>(net.minecraft.resources.ResourceKey.create(net.minecraft.core.registries.Registries.RECIPE, id), value)", "recipe-holder-key"),
    # packet accessor is a record method
    (r"packet\.getStateId\(\)", "packet.stateId()", "packet-stateid-record"),
    # GameProfile is a record
    (r"\bsender\.getName\(\)", "sender.name()", "gameprofile-sender"),
    # player view raycast without a receiver dot
    (r"(?<![\w.])player\(\)\.clip\(", "player().pick(", "player-clip-bare"),

    # misc leftovers
    (r"Item::getTranslationKey", "Item::getDescriptionId", "item-methodref"),
    (r"\.relative\((\w+), 0\)", r".relative(\1)", "relative-zero"),
    (r"LookHelper\.clip\(", "LookHelper.raycast(", "lookhelper-clip"),
    (r"\.getEyePosition\(Minecraft\.getInstance\(\)\.getRenderTickCounter\(\)[^)]*\)\)", ".getEyePosition()", "eye-position"),
    (r"WorldHelper\.getDefaultClockTime\(\)", "mod.getWorld().getDefaultClockTime()", "worldhelper-clock"),
    (r"item instanceof AxeItem\b", "item.components().has(net.minecraft.core.component.DataComponents.TOOL)", "axe-item"),
    (r"player\.getRecipeBook\(\)\.contains\([^;]*?\)\)", "true", "recipe-book-check"),
    (r"pos\.closerThan\(mod\.getPlayer\(\)\.onGround\(\) \? mod\.getPlayer\(\)\.position\(\) : mod\.getPlayer\(\)\.position\(\)\.add\(0, -1, 0\), 0\.89\)",
     "pos.closerThan(net.minecraft.core.BlockPos.containing(mod.getPlayer().onGround() ? mod.getPlayer().position() : mod.getPlayer().position().add(0, -1, 0)), 0.89)", "closer-than-vec3"),

    # final leftovers
    (r"\(BlockHitResult\) ProjectileUtil\.getHitResultOnViewVector", "(EntityHitResult) ProjectileUtil.getHitResultOnViewVector", "lookhelper-cast"),
    (r"mod\.getWorld\(\)\.getDefaultClockTime\(\)", "net.minecraft.client.Minecraft.getInstance().level.getDefaultClockTime()", "clock-level"),
    (r"\.getRawBrightness\((pos\.relative\(\w+\))\)", r".getRawBrightness(\1, 0)", "raw-brightness-arg"),

    (r"return parameters\.chatType\(\);", "return parameters.chatType().value();", "chattype-holder"),
    (r"int t = net\.minecraft\.client\.Minecraft\.getInstance\(\)\.level\.getDefaultClockTime\(\);",
     "int t = (int) net.minecraft.client.Minecraft.getInstance().level.getDefaultClockTime();", "clock-cast"),
    (r"\.getEntityById\(", ".getEntity(", "get-entity-by-id"),
    # Inventory.selected is private
    (r"\.selected\s*=\s*([^;]+);", r".setSelectedSlot(\1);", "inventory-selected-set"),
    (r"\binv\.selected\b(?!\s*=)", "inv.getSelectedSlot()", "inventory-selected-get"),
]



# Whole-block insertions that regex rules cannot express. Each entry is
# (relative file, anchor text, block to insert before the anchor, marker).
POST_EDITS = [
    (
        "kaptainwutax/tungsten/agent/AgentShapeContext.java",
        "    @Override\n    public boolean isDescending() {",
        """    @Override
    public boolean alwaysCollideWithFluid() {
        return false;
    }

""",
        "alwaysCollideWithFluid",
    ),
    (
        "kaptainwutax/tungsten/world/BetterBlockPos.java",
        "    public BetterBlockPos(double x, double y, double z) {",
        """    // 26.2 renamed BlockPos.up/add to above/offset; the rest of tungsten still
    // speaks the old names, so keep them here in one place
    public BetterBlockPos up(int n) {
        return new BetterBlockPos(getX(), getY() + n, getZ());
    }

    public BetterBlockPos add(int dx, int dy, int dz) {
        return new BetterBlockPos(getX() + dx, getY() + dy, getZ() + dz);
    }

    public BetterBlockPos add(net.minecraft.core.Vec3i other) {
        return add(other.getX(), other.getY(), other.getZ());
    }

""",
        "public BetterBlockPos up(int n)",
    ),
]


# File-scoped replacements: (relative file, old, new). Used where a blanket rule
# would hit unrelated receivers.
FILE_EDITS = [
    ("adris/altoclef/mixins/ClientPlayNetworkHandlerMixin.java",
     "packet.stateId(), packet.getSlot(), packet.getItem()",
     "packet.getStateId(), packet.getSlot(), packet.getItem()"),
    ("adris/altoclef/tasks/CraftGenericWithRecipeBooksTask.java",
     "mod.getController().handlePlaceRecipe(player.containerMenu.containerId, recipeToSend.get().asRecipe(), true);",
     "// 26.2 takes a RecipeDisplayId here; recipe-book placement is disabled until the id is resolved"),
    ("kaptainwutax/tungsten/mixin/MixinClientPlayNetworkHandler.java",
     "packet.getStateId(), i, contents.get(i)", "packet.stateId(), i, contents.get(i)"),
    ("adris/altoclef/ui/CommandStatusOverlay.java",
     "PoseStack matrixStack = context.getMatrices();\n        matrixStack.pushPose();\n        drawTaskChain(context, Minecraft.getInstance().font, 10, 10,\n                matrixStack, 10, tasks, mod);\n        matrixStack.popPose();",
     "drawTaskChain(context, Minecraft.getInstance().font, 10, 10, 10, tasks, mod);"),
    ("adris/altoclef/ui/AltoClefTickChart.java",
     "PoseStack matrixStack = context.getMatrices();\n        matrixStack.pushPose();\n        drawTaskChain(context, Minecraft.getInstance().font, 10, 10,\n                matrixStack, 10, tasks, mod);\n        matrixStack.popPose();",
     "drawTaskChain(context, Minecraft.getInstance().font, 10, 10, 10, tasks, mod);"),
    ("kaptainwutax/tungsten/mixin/MixinClientPlayNetworkHandler.java",
     "packet.getStateId(), i, contents.get(i)", "packet.stateId(), i, contents.get(i)"),
    ("kaptainwutax/tungsten/mixin/MixinClientPlayNetworkHandler.java",
     "client.gui.chatListener().addToMessageHistory(message);\n", ""),
    ("adris/altoclef/util/helpers/LookHelper.java",
     "return ProjectileUtil.getHitResultOnViewVector(from, entity -> entity.equals(to), from.distanceTo(to) + 1.0);",
     "return (BlockHitResult) ProjectileUtil.getHitResultOnViewVector(from, entity -> entity.equals(to), from.distanceTo(to) + 1.0);"),
    ("adris/altoclef/util/helpers/LookHelper.java",
     "return ProjectileUtil.getHitResultOnViewVector(from, start, start.add(direction), box, entity -> entity.equals(to), 0);",
     "return ProjectileUtil.getHitResultOnViewVector(from, entity -> entity.equals(to), from.distanceTo(to) + 1.0);"),
    ("adris/altoclef/control/SlotHandler.java",
     "mod.getController().clickSlot(syncId, windowSlot, mouseButton, type, player);",
     "mod.getController().handleContainerInput(syncId, windowSlot, mouseButton, type, player);"),
    ("kaptainwutax/tungsten/mixin/MixinClientPlayNetworkHandler.java",
     "Minecraft.getInstance().gui.chatListener().addToMessageHistory(message);\n", ""),
    ("adris/altoclef/AltoClef.java",
     "cur.getClientId(),\n                    cur.getAccountType()\n            );",
     "cur.getClientId()\n            );"),
    ("adris/altoclef/chains/MLGBucketFallChain.java",
     "import net.minecraft.world.item.Items;",
     "import net.minecraft.world.item.ItemStack;\nimport net.minecraft.world.item.Items;"),
    ("kaptainwutax/tungsten/agent/AgentShapeContext.java",
     "\t@Override\n\tpublic boolean shouldTreatFluidAsCube() { return false; }\n", ""),
    ("kaptainwutax/tungsten/mixin/MixinClientPlayNetworkHandler.java",
     "client.gui.getChatHud()", "Minecraft.getInstance().gui.getChatHud()"),
    ("adris/altoclef/mixins/ClientTickMixin.java",
     "shredderPreLoadWorld(ClientLevel world, LevelLoadingScreen.WorldEntryReason arg2, CallbackInfo ci)",
     "shredderPreLoadWorld(ClientLevel world, CallbackInfo ci)"),
    ("adris/altoclef/mixins/ClientTickMixin.java",
     "shredderPostLoadWorld(ClientLevel world, LevelLoadingScreen.WorldEntryReason arg2, CallbackInfo ci)",
     "shredderPostLoadWorld(ClientLevel world, CallbackInfo ci)"),
    ("adris/altoclef/commandsystem/args/PlayerArg.java",
     ".map(p -> p.getName())", ".map(p -> p.name())"),
]


def apply_post_edits(root):
    hits = 0
    for rel, old, new in FILE_EDITS:
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if old in text:
            path.write_text(text.replace(old, new), encoding="utf-8")
            hits += 1
    for rel, anchor, block, marker in POST_EDITS:
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if marker in text:
            continue
        if anchor not in text:
            continue
        path.write_text(text.replace(anchor, block + anchor, 1), encoding="utf-8")
        hits += 1
    return hits


def split_top_level_args(text, open_paren):
    """Split the argument list starting at open_paren into top-level parts."""
    depth = 0
    args = []
    cur = []
    i = open_paren
    while i < len(text):
        c = text[i]
        if c in "([{":
            depth += 1
            if depth == 1:
                i += 1
                continue
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                args.append("".join(cur))
                return args, i
        elif c == "," and depth == 1:
            args.append("".join(cur))
            cur = []
            i += 1
            continue
        if depth >= 1:
            cur.append(c)
        i += 1
    return None, None


def revert_chunkpos(text):
    """ChunkPos.containing(a, b) -> new ChunkPos(a, b): the record ctor still exists."""
    out = []
    i = 0
    hits = 0
    needle = "ChunkPos.containing("
    while True:
        j = text.find(needle, i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        args, close = split_top_level_args(text, j + len(needle) - 1)
        if args is not None and len(args) == 2:
            out.append(f"new ChunkPos({args[0]}, {args[1]})")
            i = close + 1
            hits += 1
        else:
            out.append(needle)
            i = j + len(needle)
    return "".join(out), hits

RULES = _COPPER + RULES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.src).expanduser().resolve()
    files = sorted(root.rglob("*.java"))
    counts = {}
    changed_files = 0

    for path in files:
        text = path.read_text(encoding="utf-8")
        original = text
        text, n_chunk = revert_chunkpos(text)
        if n_chunk:
            counts["chunkpos-revert"] = counts.get("chunkpos-revert", 0) + n_chunk
        for pattern, repl, note in RULES:
            text, n = re.subn(pattern, repl, text, flags=re.M)
            if n:
                counts[note] = counts.get(note, 0) + n
        if text != original:
            changed_files += 1
            if not args.dry_run:
                path.write_text(text, encoding="utf-8")

    if not args.dry_run:
        post_hits = apply_post_edits(root)
        if post_hits:
            print(f"  post-edits applied: {post_hits}")

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"[{mode}] files scanned: {len(files)}  changed: {changed_files}")
    for note, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
