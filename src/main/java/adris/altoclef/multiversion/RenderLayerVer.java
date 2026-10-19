package adris.altoclef.multiversion;

import net.minecraft.client.renderer.rendertype.RenderType;

public class RenderLayerVer {

    /** 26.2 has no shared GUI overlay render type; callers pass null to mean "default". */
    public static RenderType getGuiOverlay() {
        return null;
    }
}
