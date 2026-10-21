package kaptainwutax.tungsten.mixin;

import static kaptainwutax.tungsten.commandsystem.suggestionsapi.Filtering.FilteringMode.LOOSE;
import static kaptainwutax.tungsten.commandsystem.suggestionsapi.Filtering.FilteringMode.SLIGHTLY_LOOSE;
import static kaptainwutax.tungsten.commandsystem.suggestionsapi.Filtering.FilteringMode.STRICT;

import java.util.List;
import java.util.Locale;
import java.util.concurrent.CompletableFuture;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.jetbrains.annotations.Nullable;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import org.spongepowered.asm.mixin.injection.callback.LocalCapture;

import com.google.common.base.Strings;
import com.google.common.collect.Lists;
import com.mojang.brigadier.ParseResults;
import com.mojang.brigadier.StringReader;
import com.mojang.brigadier.suggestion.Suggestion;
import com.mojang.brigadier.suggestion.Suggestions;

import kaptainwutax.tungsten.TungstenMod;
import kaptainwutax.tungsten.commandsystem.CommandExecutor;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.CommandSuggestions;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.commands.SharedSuggestionProvider;

@Mixin(CommandSuggestions.class)
public abstract class MixinChatInputSuggestor {
    @Shadow private ParseResults<SharedSuggestionProvider> currentParse;
    @Shadow boolean keepSuggestions;
    @Shadow private net.minecraft.client.gui.components.CommandSuggestions.SuggestionsList suggestions;
	@Shadow private static int getLastWordIndex(String input) {
		throw new AssertionError();
	}
	@Shadow @Final EditBox textField;
	
	@Shadow
    @Nullable
    private CompletableFuture<Suggestions> pendingSuggestions;
    @Shadow
    @Final
    private boolean slashOptional;
    
    private static final Pattern COMMAND_PATTERN = Pattern.compile("^(@)");
    private static final Pattern WHITESPACE_PATTERN = Pattern.compile("(\\s+)");
    

    @Shadow
    public abstract void showSuggestions(boolean narrateFirstSuggestion);
    

    @Shadow
    protected abstract void updateUsageInfo();

    @Inject(method = "sortSuggestions", at = @At("HEAD"), cancellable = true)
	private List<Suggestion> sortSuggestions(Suggestions suggestions, CallbackInfoReturnable<List<Suggestion>> ci) {
		String command = textField.getValue().substring(0, textField.getCursorPosition());

    	ci.cancel();
		// To make sorting command literals work
		if (command.startsWith("/") || command.startsWith(TungstenMod.getCommandPrefix()))
			command = command.substring(1);
		int startOfCurrentWord = getLastWordIndex(command);
		String remaining = command.substring(startOfCurrentWord);
		// To make sorting tags work
		if (remaining.startsWith("#"))
			remaining = remaining.substring(1);
		List<Suggestion> strictList = Lists.newArrayList();
		List<Suggestion> slightlyLooseList = Lists.newArrayList();
		List<Suggestion> looseList = Lists.newArrayList();
		List<Suggestion> veryLooseList = Lists.newArrayList();

		if (remaining.contains(":"))
			remaining = remaining.substring(remaining.indexOf(':') + 1);
		remaining = remaining.toLowerCase(Locale.ROOT);

		for(Suggestion suggestion : suggestions.getList()) {
			String suggestionText = suggestion.getText();
			if (suggestionText.contains(":"))
				suggestionText = suggestionText.substring(suggestionText.indexOf(':') + 1);
			suggestionText = suggestionText.toLowerCase(Locale.ROOT);

			if (STRICT.test(remaining, suggestionText))
				strictList.add(suggestion);
			else if (SLIGHTLY_LOOSE.test(remaining, suggestionText))
				slightlyLooseList.add(suggestion);
			else if (LOOSE.test(remaining, suggestionText))
				looseList.add(suggestion);
			else
				veryLooseList.add(suggestion);
		}

		strictList.addAll(slightlyLooseList);
		strictList.addAll(looseList);
		strictList.addAll(veryLooseList);
    	ci.setReturnValue(strictList);
		return strictList;
	}


	@Inject(method = "updateCommandInfo", at = @At(value = "INVOKE", target = "Lcom/mojang/brigadier/StringReader;canRead()Z", remap = false),
	        cancellable = true,
	        locals = LocalCapture.CAPTURE_FAILHARD)
    private void inject(CallbackInfo ci, String string, StringReader reader) {
		if (TungstenMod.mc == null) return; // tungsten not initialized yet
		String prefix = TungstenMod.getCommandPrefix();
        int length = prefix.length();

        if (reader.canRead(length) && reader.getString().startsWith(prefix, reader.getCursor())) {
            String message = reader.getString();
            reader.setCursor(reader.getCursor() + length);

            if (this.currentParse == null) {
            	TungstenMod.getCommandExecutor();
                if (message.contains("|")) {
                	// ⛔ FIXED 2026-09-05: `message.split("|")` treats "|" as a regex alternation
                	// between two empty patterns, matching a zero-width string at every position --
                	// splits between EVERY CHARACTER instead of on the literal pipe divider this
                	// chained-command feature uses. `[...length-1]` on the broken split just returns
                	// the message's last single character instead of the text after the last real
                	// "|", so suggestions/parsing for a chained command like ";stop|;goto 1" were
                	// built from "1" alone rather than ";goto 1" as intended. Same bug, same fix, as
                	// the live one already found in MixinClientPlayNetworkHandler.onSendChatMessage.
                	String[] segments = message.split("\\|");
                	this.currentParse = CommandExecutor.DISPATCHER.parse(new StringReader(segments[segments.length-1]), TungstenMod.mc.getConnection().getSuggestionsProvider());
                } else
                	this.currentParse = CommandExecutor.DISPATCHER.parse(reader, TungstenMod.mc.getConnection().getSuggestionsProvider());
            }

            int cursor = textField.getCursorPosition();
            if (cursor >= length && (this.suggestions == null || !this.keepSuggestions)) {
            	TungstenMod.getCommandExecutor();
                if (message.contains("|")) {
                	// ⛔ FIXED 2026-09-05: same split("|") bug as above.
                	String[] segments = message.split("\\|");
                	this.pendingSuggestions = CommandExecutor.DISPATCHER.getCompletionSuggestions(this.currentParse, new StringReader(segments[segments.length-1]).getTotalLength());
                } else
                	this.pendingSuggestions = CommandExecutor.DISPATCHER.getCompletionSuggestions(this.currentParse, cursor);
                this.pendingSuggestions.thenRun(() -> {
                    if (this.pendingSuggestions.isDone()) {
                        this.updateUsageInfo();
                    }
                });
            }

            ci.cancel();
        }
    }
	
	 private int getLastPattern(String input, Pattern pattern) {
	        if (Strings.isNullOrEmpty(input)) {
	            return 0;
	        }
	        int i = 0;
	        Matcher matcher = pattern.matcher(input);
	        while (matcher.find()) {
	            i = matcher.end();
	        }
	        return i;
	    }
}