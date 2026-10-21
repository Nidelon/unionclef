package adris.altoclef.util.helpers;

import net.minecraft.client.Minecraft;
import com.mojang.blaze3d.platform.InputConstants;

public class InputHelper {

    public static boolean isKeyPressed(int code) {
        //#if MC < 12111
        return InputConstants.isKeyDown(Minecraft.getInstance().getWindow(), code);
        //#else
        //$$ return InputConstants.isKeyDown(Minecraft.getInstance().getWindow(), code); // TODO [1.21.11] isKeyPressed(long, int) → isKeyPressed(Window, int)
        //#endif
    }
}
