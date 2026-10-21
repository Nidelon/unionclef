package adris.altoclef.multiversion.entity;

import adris.altoclef.multiversion.Pattern;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import java.util.List;

public class LivingEntityVer {

    @SuppressWarnings("unchecked")
    private static Iterable<ItemStack> reflectMethod(LivingEntity entity, String name) {
        try {
            return (Iterable<ItemStack>) LivingEntity.class.getMethod(name).invoke(entity);
        } catch (Exception e) {
            return List.of();
        }
    }

    static Iterable<ItemStack> callEquippedItems(LivingEntity e) { return reflectMethod(e, "getEquippedItems"); }
    static Iterable<ItemStack> callHandItems(LivingEntity e) { return reflectMethod(e, "getHandItems"); }
    static Iterable<ItemStack> callArmorItems(LivingEntity e) { return reflectMethod(e, "getArmorItems"); }

    public static boolean hasTrident(LivingEntity entity) {
        //#if MC >= 12111
        //$$ return entity.getMainHandStack().isOf(Items.TRIDENT)
        //$$     || entity.getOffHandStack().isOf(Items.TRIDENT);
        //#else
        for (ItemStack stack : callEquippedItems(entity)) {
            if (stack.is(Items.TRIDENT)) return true;
        }
        return false;
        //#endif
    }

    @Pattern
    private static boolean isSuitableFor(Item item, BlockState state) {
        //#if MC >= 12005
        return item.getDefaultInstance().isCorrectToolForDrops(state);
        //#else
        //$$ return item.isSuitableFor(state);
        //#endif
    }

}
