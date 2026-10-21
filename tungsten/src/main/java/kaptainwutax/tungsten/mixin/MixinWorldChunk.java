package kaptainwutax.tungsten.mixin;

import java.util.function.Consumer;

import org.jetbrains.annotations.Nullable;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import kaptainwutax.tungsten.TungstenModDataContainer;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.FluidState;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.protocol.game.ClientboundLevelChunkPacketData;
import net.minecraft.core.Registry;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.LevelChunkSection;
import net.minecraft.world.level.chunk.UpgradeData;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.levelgen.blending.BlendingData;

@Mixin(LevelChunk.class)
public abstract class MixinWorldChunk extends ChunkAccess {

	//#if MC < 12111
	//$$ public MixinWorldChunk(ChunkPos pos, UpgradeData upgradeData, LevelHeightAccessor heightLimitView, Registry<Biome> biome,
	                       //$$ long inhabitedTime, @Nullable LevelChunkSection[] sectionArrayInitializer, @Nullable BlendingData blendingData) {
		//$$ super(pos, upgradeData, heightLimitView, biome, inhabitedTime, sectionArrayInitializer, blendingData);
	//$$ }
	//#else
	public MixinWorldChunk(ChunkPos pos, UpgradeData upgradeData, LevelHeightAccessor heightLimitView, net.minecraft.world.level.chunk.PalettedContainerFactory palettesFactory,
	                       long inhabitedTime, @Nullable LevelChunkSection[] sectionArrayInitializer, @Nullable BlendingData blendingData) {
	    super(pos, upgradeData, heightLimitView, palettesFactory, inhabitedTime, sectionArrayInitializer, blendingData);
	}
	//#endif

	@Shadow public abstract Level getLevel();
	@Shadow public abstract BlockState getBlockState(BlockPos pos);
	@Shadow public abstract FluidState getFluidState(BlockPos pos);

	@Inject(method = "replaceWithPacketData", at = @At("RETURN"))
	//#if MC < 12111
	//$$ private void loadFromPacket(FriendlyByteBuf buf, CompoundTag nbt, Consumer<net.minecraft.network.protocol.game.ClientboundLevelChunkPacketData.BlockEntityTagOutput> consumer, CallbackInfo ci) {
	//#else
	private void loadFromPacket(FriendlyByteBuf buf, java.util.Map nbt, Consumer<net.minecraft.network.protocol.game.ClientboundLevelChunkPacketData.BlockEntityTagOutput> consumer, CallbackInfo ci) {
	//#endif
		if(this.getLevel() != TungstenModDataContainer.world) {
			TungstenModDataContainer.world = this.getLevel();
		}
	}

}
