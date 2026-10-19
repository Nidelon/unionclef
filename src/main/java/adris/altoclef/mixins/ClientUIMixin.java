package adris.altoclef.mixins;

import adris.altoclef.eventbus.EventBus;
import adris.altoclef.eventbus.events.ClientRenderEvent;
import adris.altoclef.multiversion.DrawContextWrapper;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.Gui;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Gui.class)
public final class ClientUIMixin {
    // 26.2: extractRenderState no longer receives the draw context, so the
    // overlay event fires without one and the in-game overlays stay dark.
    @Inject(method = "extractRenderState", at = @At("TAIL"))
    private void clientRender(DeltaTracker tickCounter, boolean first, boolean second,
                              CallbackInfo ci) {
        EventBus.publish(new ClientRenderEvent(DrawContextWrapper.of(null),
                tickCounter.getGameTimeDeltaPartialTick(true)));
    }
}
