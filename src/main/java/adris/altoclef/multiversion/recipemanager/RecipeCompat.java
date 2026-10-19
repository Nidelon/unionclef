package adris.altoclef.multiversion.recipemanager;

import net.minecraft.client.Minecraft;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraft.world.item.crafting.display.SlotDisplayContext;

/**
 * Recipe helpers for the 26.2 model.
 * <p>
 * 26.2 removed {@code Recipe.getResult(RegistryAccess)}; the output is now a
 * {@code SlotDisplay} reachable through {@code Recipe.display()}, and it has to
 * be resolved against the level's registries.
 */
public final class RecipeCompat {

    private RecipeCompat() {
    }

    public static ItemStack resultOf(Recipe<?> recipe) {
        try {
            var level = Minecraft.getInstance().level;
            if (level == null) {
                return ItemStack.EMPTY;
            }
            return recipe.display().result()
                    .resolveForFirstStack(SlotDisplayContext.fromLevel(level));
        } catch (Exception e) {
            return ItemStack.EMPTY;
        }
    }
}
