package adris.altoclef.multiversion;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphicsExtractor;
import org.jetbrains.annotations.Nullable;
import org.joml.Matrix3x2fStack;

/**
 * Thin wrapper over the GUI draw context, written against the 26.2 API.
 * <p>
 * 26.2 replaced {@code GuiGraphics} with {@code GuiGraphicsExtractor}, moved the
 * pose stack to {@code Matrix3x2fStack}, and dropped the per-call render layer.
 * The wrapper keeps the call shape the rest of the mod already uses.
 */
public class DrawContextWrapper {

    public static DrawContextWrapper of(GuiGraphicsExtractor context) {
        // callers may have no context (26.2 does not hand one to the HUD hook);
        // every draw then silently does nothing instead of throwing
        return new DrawContextWrapper(context);
    }

    private final GuiGraphicsExtractor context;

    private DrawContextWrapper(GuiGraphicsExtractor context) {
        this.context = context;
    }

    /** Kept for callers that used to pick a render layer; the new API decides itself. */
    public void setRenderLayer(Object renderLayer) {
    }

    public void fill(int x1, int y1, int x2, int y2, int color) {
        if (context == null) {
            return;
        }
        context.fill(x1, y1, x2, y2, color);
    }

    public void drawHorizontalLine(int x1, int x2, int y, int color) {
        if (context == null) {
            return;
        }
        context.fill(Math.min(x1, x2), y, Math.max(x1, x2) + 1, y + 1, color);
    }

    public void drawVerticalLine(int x, int y1, int y2, int color) {
        if (context == null) {
            return;
        }
        context.fill(x, Math.min(y1, y2), x + 1, Math.max(y1, y2) + 1, color);
    }
    public void drawText(Font textRenderer, @Nullable String text, int x, int y,
                         int color, boolean shadow) {
        if (text == null || context == null) {
            return;
        }
        context.text(textRenderer, text, x, y, color, shadow);
    }

    public Matrix3x2fStack getMatrices() {
        return context == null ? new Matrix3x2fStack(1) : context.pose();
    }

    public int getScaledWindowWidth() {
        return Minecraft.getInstance().getWindow().getGuiScaledWidth();
    }

    public int getScaledWindowHeight() {
        return Minecraft.getInstance().getWindow().getGuiScaledHeight();
    }
}
