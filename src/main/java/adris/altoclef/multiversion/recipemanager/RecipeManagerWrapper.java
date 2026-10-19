package adris.altoclef.multiversion.recipemanager;

import net.minecraft.world.item.crafting.RecipeAccess;

import java.util.Collection;
import java.util.Collections;

/**
 * Access to the client's recipe list.
 * <p>
 * 26.2 no longer exposes recipe enumeration on the client: {@code RecipeManager}
 * is server-side, and {@code ClientPacketListener.recipes()} hands out a
 * {@code RecipeAccess} that can look recipes up but not list them. The client's
 * only full list lives in {@code ClientRecipeBook}, which is fed by the recipe
 * book packets and is not reachable from here without a mixin.
 * <p>
 * TODO: tap {@code ClientRecipeBook} so recipe-driven crafting works again.
 */
public class RecipeManagerWrapper {

    private final RecipeAccess recipeAccess;

    public static RecipeManagerWrapper of(RecipeAccess recipeAccess) {
        if (recipeAccess == null) {
            return null;
        }
        return new RecipeManagerWrapper(recipeAccess);
    }

    private RecipeManagerWrapper(RecipeAccess recipeAccess) {
        this.recipeAccess = recipeAccess;
    }

    public Collection<WrappedRecipeEntry> values() {
        return Collections.emptySet();
    }
}
