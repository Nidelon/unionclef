package adris.altoclef.multiversion;

import net.minecraft.util.ARGB;

public class ColorHelperVer {
    public static int getAlpha(int color) {
        //#if MC >= 12111
        //$$ return FastColor.getAlpha(color);
        //#else
        return ARGB.alpha(color);
        //#endif
    }
    public static int getRed(int color) {
        //#if MC >= 12111
        //$$ return FastColor.getRed(color);
        //#else
        return ARGB.red(color);
        //#endif
    }
    public static int getGreen(int color) {
        //#if MC >= 12111
        //$$ return FastColor.getGreen(color);
        //#else
        return ARGB.green(color);
        //#endif
    }
    public static int getBlue(int color) {
        //#if MC >= 12111
        //$$ return FastColor.getBlue(color);
        //#else
        return ARGB.blue(color);
        //#endif
    }
    public static int getArgb(int a, int r, int g, int b) {
        //#if MC >= 12111
        //$$ return FastColor.getArgb(a, r, g, b);
        //#else
        return ARGB.color(a, r, g, b);
        //#endif
    }
}
