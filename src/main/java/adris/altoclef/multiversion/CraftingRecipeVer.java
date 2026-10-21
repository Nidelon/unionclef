package adris.altoclef.multiversion;

import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.CraftingRecipe;

public class CraftingRecipeVer {


    public static ItemStack getOutput(CraftingRecipe craftingRecipe) {
        //#if MC >= 12111
        //$$ return ItemStack.EMPTY; // TODO [1.21.11] Recipe.getResult() API changed
        //#elseif MC >= 11904
        return adris.altoclef.multiversion.recipemanager.RecipeCompat.resultOf(craftingRecipe);
        //#else
        //$$ return craftingRecipe.getOutput();
        //#endif
    }

}
