package adris.altoclef.multiversion.item;

import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.item.Item;
//#if MC < 12111
//#endif

import java.util.Set;

public class ItemHelper {


    //#if MC <= 11605
    //$$ public static boolean isSuitableFor(Item item, BlockState state){
    //$$     if (item instanceof PickaxeItem pickaxe) {
    //$$         return pickaxe.isSuitableFor(state);
    //$$     }
    //$$
    //$$     if (item instanceof DiggerItem) {
    //$$         boolean isInEffectiveBlocks = ((MiningToolItemAccessor)item).getEffectiveBlocks().contains(state.getBlock());
    //$$
    //$$         if (item.components().has(net.minecraft.core.component.DataComponents.TOOL)) {
    //$$             return isInEffectiveBlocks || ((AxeItemAccessor)item).getEffectiveMaterials().contains(state.getMaterial());
    //$$         }
    //$$         return isInEffectiveBlocks;
    //$$     }
    //$$
    //$$     return item.isSuitableFor(state);
    //$$ }
    //$$
    //#endif

}
