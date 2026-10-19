package adris.altoclef.mixins;

import adris.altoclef.AltoClef;
import adris.altoclef.ui.EpicCamera;
import net.minecraft.client.Camera;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Camera.class)
public abstract class CameraMixin {
    @Shadow protected abstract void setPosition(double x, double y, double z);
    @Shadow protected abstract void setRotation(float yaw, float pitch);
    @Shadow private Entity entity;

    // 26.2: update() takes only the delta tracker; the focused entity and the
    // perspective now come from the camera's own field and the client options.
    @Inject(at = @At("TAIL"), method = "update")
    private void onUpdate(DeltaTracker tracker, CallbackInfo ci) {
        Entity focusedEntity = this.entity;
        boolean thirdPerson = !Minecraft.getInstance().options.getCameraType().isFirstPerson();
        float tickDelta = tracker.getGameTimeDeltaPartialTick(true);
        if (thirdPerson
                && focusedEntity != null
                && AltoClef.getInstance() != null
                && AltoClef.getInstance().getModSettings().isEpicCameraEnabled()) {
            var update = EpicCamera.getInstance().getUpdate(
                    focusedEntity, tickDelta,
                    AltoClef.getCameraRotationModifer(),
                    AltoClef.getCameraPositionModifer());
            if (update != null) {
                setPosition(update.getPosition().x, update.getPosition().y, update.getPosition().z);
                setRotation(update.getYaw(), update.getPitch());
            }
        } else {
            EpicCamera.getInstance().reset();
        }
    }
}
