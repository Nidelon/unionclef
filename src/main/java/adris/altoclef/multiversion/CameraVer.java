package adris.altoclef.multiversion;

import net.minecraft.client.Camera;
import net.minecraft.world.phys.Vec3;

public class CameraVer {
    @Pattern
    private static Vec3 getPos(Camera camera) {
        //#if MC >= 12111
        //$$ return camera.getCameraPos();
        //#else
        return camera.position();
        //#endif
    }
}
