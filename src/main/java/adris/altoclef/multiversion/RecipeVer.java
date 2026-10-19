package adris.altoclef.multiversion;

import adris.altoclef.multiversion.recipemanager.RecipeCompat;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraft.world.level.Level;

public class RecipeVer {

    public static ItemStack getOutput(Recipe<?> recipe, Level world) {
        return RecipeCompat.resultOf(recipe);
    }
}
