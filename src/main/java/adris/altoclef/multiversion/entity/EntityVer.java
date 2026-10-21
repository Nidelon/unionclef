package adris.altoclef.multiversion.entity;

import adris.altoclef.multiversion.Pattern;
import net.fabricmc.loader.impl.lib.sat4j.core.Vec;
import net.minecraft.world.entity.Entity;
import adris.altoclef.mixins.EntityAccessor;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.Vec3;

public class EntityVer {


    @Pattern
    public boolean isInNetherPortal(Entity entity) {
        //#if MC <= 12006
        //$$ return ((EntityAccessor)entity).isInNetherPortal();
        //#else
        return adris.altoclef.multiversion.entity.EntityHelper.isInNetherPortal(entity);
        //#endif
    }

    @Pattern
    public int getPortalCooldown(Entity entity) {
        //#if MC >= 12001
        return entity.getPortalCooldown();
        //#else
        //$$ return ((EntityAccessor) entity).getPortalCooldown();
        //#endif
    }


    @Pattern
    public BlockPos getLandingPos(Entity entity) {
        //#if MC >= 11701
        return entity.getOnPos();
        //#else
        //$$ return ((adris.altoclef.mixins.EntityAccessor) entity).invokeGetLandingPos();
        //#endif
    }

    @Pattern
    private static float getPitch(Entity player) {
        //#if MC >= 11701
        return player.getXRot(1.0f);
        //#else
        //$$ return player.pitch;
        //#endif
    }

    @Pattern
    private static float getYaw(Entity player) {
        //#if MC >= 11701
        return player.getYRot(1.0f);
        //#else
        //$$ return player.yaw;
        //#endif
    }

    @Pattern
    private static void setPitch(Entity player, float value) {
        //#if MC >= 11701
        player.setXRot(value);
        //#else
        //$$ player.pitch = value;
        //#endif
    }

    @Pattern
    private static void setYaw(Entity player, float value) {
        //#if MC >= 11701
        player.setYRot(value);
        //#else
        //$$ player.yaw = value;
        //#endif
    }

    @Pattern
    private static Vec3 getEyePos(Entity entity) {
        //#if MC >= 11701
        return entity.getEyePosition();
        //#else
        //$$ return adris.altoclef.multiversion.entity.EntityHelper.getEyePos(entity);
        //#endif
    }

    @Pattern
    private static ChunkPos getChunkPos(Entity entity) {
        //#if MC >= 11701
        return entity.chunkPosition();
        //#else
        //$$ return adris.altoclef.multiversion.entity.EntityHelper.getChunkPos(entity);
        //#endif
    }

    @Pattern
    private static int getBlockX(Entity entity) {
        //#if MC >= 11701
        return entity.getBlockX();
        //#else
        //$$ return adris.altoclef.multiversion.entity.EntityHelper.getBlockX(entity);
        //#endif
    }

    @Pattern
    private static int getBlockY(Entity entity) {
        //#if MC >= 11701
        return entity.getBlockY();
        //#else
        //$$ return adris.altoclef.multiversion.entity.EntityHelper.getBlockY(entity);
        //#endif
    }

    @Pattern
    private static int getBlockZ(Entity entity) {
        //#if MC >= 11701
        return entity.getBlockZ();
        //#else
        //$$ return adris.altoclef.multiversion.entity.EntityHelper.getBlockZ(entity);
        //#endif
    }

    @Pattern
    private static Vec3 getPos(Entity entity) {
        //#if MC >= 12111
        //$$ return entity.getEntityPos();
        //#else
        return entity.position();
        //#endif
    }

    @Pattern
    private static net.minecraft.world.level.Level getWorld(Entity entity) {
        //#if MC >= 12111
        //$$ return entity.level();
        //#else
        return entity.level();
        //#endif
    }

    // getHandItems/getArmorItems deleted in 1.21.11.
    // Preprocessor crashes remapping deleted methods, even in inactive #if.
    // Use reflection on 1.21.1 to hide identifiers from preprocessor.
    public static Iterable<net.minecraft.world.item.ItemStack> getHandItems(net.minecraft.world.entity.LivingEntity entity) {
        //#if MC >= 12111
        //$$ return java.util.List.of(entity.getMainHandStack(), entity.getOffHandStack());
        //#else
        return LivingEntityVer.callHandItems(entity);
        //#endif
    }

    public static Iterable<net.minecraft.world.item.ItemStack> getArmorItems(net.minecraft.world.entity.LivingEntity entity) {
        //#if MC >= 12111
        //$$ return java.util.List.of(
        //$$     entity.getEquippedStack(net.minecraft.world.entity.EquipmentSlot.HEAD),
        //$$     entity.getEquippedStack(net.minecraft.world.entity.EquipmentSlot.CHEST),
        //$$     entity.getEquippedStack(net.minecraft.world.entity.EquipmentSlot.LEGS),
        //$$     entity.getEquippedStack(net.minecraft.world.entity.EquipmentSlot.FEET)
        //$$ );
        //#else
        return LivingEntityVer.callArmorItems(entity);
        //#endif
    }

}
