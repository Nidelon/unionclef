package adris.altoclef.multiversion.recipemanager;

import net.minecraft.world.item.crafting.Recipe;
//#if MC>12001
import net.minecraft.world.item.crafting.RecipeHolder;
//#endif
import net.minecraft.resources.Identifier;

public record WrappedRecipeEntry(Identifier id, Recipe<?> value) {

    //#if MC >= 12111
    //$$ public RecipeHolder<?> asRecipe() {
    //$$     return null; // TODO [1.21.11] RecipeHolder constructor takes RegistryKey now
    //$$ }
    //#elseif MC>12001
    public RecipeHolder<?> asRecipe() {
        return new RecipeHolder<Recipe<?>>(net.minecraft.resources.ResourceKey.create(net.minecraft.core.registries.Registries.RECIPE, id), value);
    }
    //#else
    //$$ public Recipe<?> asRecipe(){
    //$$     return value;
    //$$ }
    //#endif

}
