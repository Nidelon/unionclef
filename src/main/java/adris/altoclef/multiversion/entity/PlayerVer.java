package adris.altoclef.multiversion.entity;

import adris.altoclef.multiversion.Pattern;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.Container;
import net.minecraft.world.item.ItemStack;

public class PlayerVer {


    public static void sendChatMessage(LocalPlayer player,String content) {
        //#if MC >= 11904
        player.connection.sendChat(content);
        //#else
        //$$ player.sendChatMessage(content);
        //#endif
    }

    public static void sendChatCommand(LocalPlayer player,String content) {
        //#if MC >= 11904
        player.connection.sendCommand(content);
        //#else
        //$$ player.sendChatMessage("/"+content);
        //#endif
    }

    @Pattern
    private static ItemStack getCursorStack(Player player) {
        //#if MC >= 11701
        return player.containerMenu.getCarried();
        //#else
        //$$ return player.inventory.getCursorStack();
        //#endif
    }

    @Pattern
    private static Container getInventory(Player player) {
        //#if MC >= 11701
        return player.getInventory();
        //#else
        //$$ return player.inventory;
        //#endif
    }

    public static boolean inPowderedSnow(Player player) {
        //#if MC >= 11701
        return player.isInPowderSnow;
        //#else
        //$$ return false;
        //#endif
    }

    @Pattern
    public static int getSelectedSlot(net.minecraft.world.entity.player.Inventory inv) {
        //#if MC >= 12111
        //$$ return inv.getSelectedSlot();
        //#else
        return inv.getSelectedSlot();
        //#endif
    }

    /**
     * ⛔ SYNCS THE SLOT TO THE SERVER TOO, because every caller here is one swing away from the
     * race this shim used to hide: the field is written locally and vanilla posts the packet on
     * its own tick, so anything acting in the same tick acts with the PREVIOUS item. Measured on
     * allround as ~12 hits of exactly 1.0 hp a run -- a bow's attack damage -- with an iron_sword
     * drawn on the client. Behind syncSlotToServer while it is being measured.
     */
    public static void setSelectedSlot(net.minecraft.world.entity.player.Inventory inv, int slot) {
        //#if MC >= 12111
        //$$ inv.setSelectedSlot(slot);
        //#else
        inv.setSelectedSlot(slot);
        //#endif
        net.minecraft.client.Minecraft mc = net.minecraft.client.Minecraft.getInstance();
        if (mc.player != null && mc.player.getInventory() == inv) {
            kaptainwutax.tungsten.combat.WeaponSelector.syncSlot(mc.player, slot);
        }
    }

}
