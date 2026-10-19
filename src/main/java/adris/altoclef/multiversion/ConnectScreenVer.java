package adris.altoclef.multiversion;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.ConnectScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.client.multiplayer.TransferState;
import net.minecraft.client.multiplayer.resolver.ServerAddress;

import java.util.Map;

public class ConnectScreenVer {

    public static void connect(Screen screen, Minecraft client, ServerAddress address,
                               ServerData info, boolean quickPlay) {
        ConnectScreen.startConnecting(screen, client, address, info, quickPlay,
                new TransferState(Map.of(), Map.of(), false));
    }
}
