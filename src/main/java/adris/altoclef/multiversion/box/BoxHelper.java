package adris.altoclef.multiversion.box;

import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

public class BoxHelper {

    //#if MC <= 11605
    //$$ public static AABB of(Vec3 center, double dx, double dy, double dz) {
    //$$     return new AABB(center.x - dx / 2.0, center.y - dy / 2.0, center.z - dz / 2.0, center.x + dx / 2.0, center.y + dy / 2.0, center.z + dz / 2.0);
    //$$ }
    //#endif

}
