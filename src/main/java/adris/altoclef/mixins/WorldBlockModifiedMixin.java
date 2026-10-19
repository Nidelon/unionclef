package adris.altoclef.mixins;

import adris.altoclef.eventbus.EventBus;
import adris.altoclef.eventbus.events.BlockPlaceEvent;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Level.class)
public class WorldBlockModifiedMixin {

    @Unique
    private static boolean hasBlock(BlockState state, BlockPos pos) {
        return !state.isAir() && state.isSolidRender();
    }

    // 26.2: the old (pos, oldState, newState) hook is gone; sendBlockUpdated has
    // the same shape plus a flags argument.
    @Inject(method = "sendBlockUpdated", at = @At("HEAD"))
    public void onBlockWasChanged(BlockPos pos, BlockState oldBlock, BlockState newBlock,
                                  int flags, CallbackInfo ci) {
        if (!hasBlock(oldBlock, pos) && hasBlock(newBlock, pos)) {
            BlockPlaceEvent evt = new BlockPlaceEvent(pos, newBlock);
            EventBus.publish(evt);
        }
    }
}
