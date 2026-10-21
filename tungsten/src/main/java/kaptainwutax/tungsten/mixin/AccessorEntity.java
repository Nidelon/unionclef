package kaptainwutax.tungsten.mixin;

import java.util.Set;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.material.Fluid;
import net.minecraft.tags.TagKey;
import net.minecraft.world.phys.Vec3;

@Mixin(Entity.class)
public interface AccessorEntity {

    @org.spongepowered.asm.mixin.gen.Invoker("getVelocityAffectingPos")
    net.minecraft.core.BlockPos tungsten$getVelocityAffectingPos();

	@Accessor
	Vec3 getMovementMultiplier();

	@Accessor
	boolean getFirstUpdate();

	@Accessor
	Set<TagKey<Fluid>> getSubmergedFluidTag();

}
