package kaptainwutax.tungsten.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

import net.minecraft.client.gui.components.CommandSuggestions;
import net.minecraft.client.gui.components.EditBox;

@Mixin(CommandSuggestions.class)
public interface AccessorChatInputSuggestor {
	 @Accessor
    EditBox getTextField();
}
