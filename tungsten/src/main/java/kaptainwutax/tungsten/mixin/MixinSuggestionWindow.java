package kaptainwutax.tungsten.mixin;

import java.util.List;

import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import com.mojang.brigadier.suggestion.Suggestion;

import kaptainwutax.tungsten.TungstenMod;
import kaptainwutax.tungsten.helpers.StringProcessorHelper;
import net.minecraft.client.gui.components.CommandSuggestions;
import net.minecraft.client.gui.components.EditBox;

@Mixin(net.minecraft.client.gui.components.CommandSuggestions.SuggestionsList.class)
public class MixinSuggestionWindow {
	@Shadow
    @Final
    CommandSuggestions field_21615;
    @Shadow
    private int current;
    @Shadow
    @Final
    private List<Suggestion> suggestions;
    
    @Inject(method = "useSuggestion", at = @At("HEAD"), cancellable = true)
    private void overwriteComplete(CallbackInfo ci) {
    	AccessorChatInputSuggestor inputSuggestor = (AccessorChatInputSuggestor) this.field_21615;
        if (inputSuggestor == null) return;
        EditBox textFieldWidget = inputSuggestor.getTextField();
        Suggestion suggestion = this.suggestions.get(this.current);
        int just = suggestion.getRange().getStart() + suggestion.getText().length();
            if (textFieldWidget.getValue().contains("|")) {
            	int closestIDXOfDivider = StringProcessorHelper.findClosestCharIndex(textFieldWidget.getValue(), '|', textFieldWidget.getCursorPosition()-1);
                if (TungstenMod.getCommandExecutor().allCommands().stream().anyMatch(cmd -> cmd.getName().equals(suggestion.getText()))) {
	                textFieldWidget.deleteChars(closestIDXOfDivider+1 - textFieldWidget.getCursorPosition());
                } else {
                	closestIDXOfDivider = StringProcessorHelper.findClosestCharIndex(textFieldWidget.getValue(), ' ', textFieldWidget.getCursorPosition()-1);
                	textFieldWidget.deleteChars(closestIDXOfDivider+1 - textFieldWidget.getCursorPosition());
                }
                textFieldWidget.setHighlightPos(textFieldWidget.getValue().length());
                textFieldWidget.insertText(suggestion.getText());
                ci.cancel();
            }
    }
}

