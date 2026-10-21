package kaptainwutax.tungsten.mixin;

import org.jetbrains.annotations.Nullable;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import kaptainwutax.tungsten.TungstenModDataContainer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.multiplayer.ClientLevel;

@Mixin(Minecraft.class)
public class MixinMinecraftClient {

	@Shadow @Nullable public ClientLevel world;
	@Shadow @Nullable public GameRenderer gameRenderer;

	@Inject(at = @At("HEAD"), method = "tick")
	private void tick(CallbackInfo info) {
		if (gameRenderer != TungstenModDataContainer.gameRenderer) {
	        TungstenModDataContainer.gameRenderer = this.gameRenderer;
		}
		if (Minecraft.getInstance().player != TungstenModDataContainer.player) {
	        TungstenModDataContainer.player = Minecraft.getInstance().player;
		}
	}
	
}
