package adris.altoclef.mixins;

import adris.altoclef.eventbus.EventBus;
import adris.altoclef.eventbus.events.ClientTickEvent;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
//#if MC < 12111
import net.minecraft.client.gui.screens.LevelLoadingScreen;
//#endif
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

// Changed this from player to client, I hope this doesn't break anything.
@Mixin(Minecraft.class)
public final class ClientTickMixin {

    @Shadow
    public ClientLevel level;

    @Inject(
            method = "tick",
            at = @At("HEAD")
    )
    private void clientTick(CallbackInfo ci) {
        EventBus.publish(new ClientTickEvent());
    }

    // --- shredder joinWorld world-event bridge (preprocessed for cross-version) ---

    @Inject(method = "setLevel", at = @At("HEAD"))
    //#if MC < 12111
    private void shredderPreLoadWorld(ClientLevel world, CallbackInfo ci) {
    //#else
    //$$ private void shredderPreLoadWorld(ClientLevel world, CallbackInfo ci) {
    //#endif
    }

    @Inject(method = "setLevel", at = @At("RETURN"))
    //#if MC < 12111
    private void shredderPostLoadWorld(ClientLevel world, CallbackInfo ci) {
    //#else
    //$$ private void shredderPostLoadWorld(ClientLevel world, CallbackInfo ci) {
    //#endif
    }

    // fireShredderWorldEvent REMOVED (G-0): it existed to tell the legacy engine that a
    // world had loaded or unloaded. There is no legacy engine to tell.
}
