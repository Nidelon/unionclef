package adris.altoclef.multiversion.world;

import net.minecraft.world.level.Level;
import net.minecraft.core.BlockPos;

public class WorldHelper {

    //#if MC <= 11605
    //$$ public static int getTopY(Level world) {
    //$$     return 255;
    //$$ }
    //$$ public static int getBottomY(Level world) {
    //$$     return 0;
    //$$ }
    //$$
    //$$ public static boolean isOutOfHeightLimit(Level world,BlockPos pos) {
    //$$      return isOutOfHeightLimit(pos.getY());
    //$$   }
    //$$
    //$$ private static boolean isOutOfHeightLimit(int y) {
    //$$      return y < getBottomY(null) || y >= getTopY(null);
    //$$   }
    //#endif

}
