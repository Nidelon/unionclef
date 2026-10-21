package adris.altoclef.mixins;

import adris.altoclef.AltoClef;
import adris.altoclef.commandsystem.Command;
import adris.altoclef.commandsystem.CommandExecutor;
import adris.altoclef.commandsystem.StringReader;
import adris.altoclef.commandsystem.TabCompleter;
import adris.altoclef.commandsystem.args.Arg;
import adris.altoclef.commandsystem.args.ListArg;
import adris.altoclef.commandsystem.exception.BadCommandSyntaxException;
import adris.altoclef.commandsystem.exception.CommandException;
import adris.altoclef.commandsystem.exception.CommandNotFinishedException;
import adris.altoclef.commandsystem.exception.RuntimeCommandException;
import adris.altoclef.util.Pair;
import com.mojang.brigadier.ParseResults;
import com.mojang.brigadier.context.StringRange;
import com.mojang.brigadier.suggestion.Suggestion;
import com.mojang.brigadier.suggestion.Suggestions;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.components.CommandSuggestions;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.util.FormattedCharSequence;
import net.minecraft.network.chat.Style;
import net.minecraft.network.chat.Component;
import net.minecraft.ChatFormatting;
import net.minecraft.util.Mth;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.concurrent.CompletableFuture;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Optional;

/**
 * Mixin responsible for highlighting our custom commands.
 * This class is an absolute monstrosity, but the command system is not touched often anyway, so I will leave it like this for now.
 */
@Mixin(CommandSuggestions.class)
public abstract class ChatInputSuggestorMixin {

    @Unique
    private static final Style SEMICOLOMN_STYLE = Style.EMPTY.withColor(ChatFormatting.LIGHT_PURPLE);
    @Shadow
    @Final
    private static Style ERROR_STYLE;
    @Shadow
    @Final
    private static Style INFO_STYLE;
    @Shadow
    @Final
    private static List<Style> HIGHLIGHT_STYLES;
    @Shadow
    @Final
    private EditBox textField;
    @Shadow
    @Final
    private List<FormattedCharSequence> messages;

    @Shadow
    private int commandUsageWidth;
    @Shadow
    @Final
    private Screen owner;

    @Shadow
    private int commandUsagePosition;
    @Shadow
    @Final
    private Font textRenderer;

    @Shadow
    private ParseResults currentParse;

    @Shadow
    private CompletableFuture<Suggestions> pendingSuggestions;

    @Shadow
    private net.minecraft.client.gui.components.CommandSuggestions.SuggestionsList suggestions;

    @Shadow
    boolean keepSuggestions;

    @Unique
    private final HashMap<Pair<String, Integer>, Pair<MutableComponent, Optional<Pair<MutableComponent, Integer>>>> parseCache = new HashMap<>();

    @Unique
    private static String addStyledText(List<Pair<String, Style>> styledText, String original, String currentStr, Style style, StringReader reader) throws CommandException {
        if (!reader.hasNext()) {
            styledText.add(new Pair<>(currentStr, style));
            return "";
        }

        int diff = original.length() - currentStr.length();
        int index = reader.getIndex() - diff;
        String processed = currentStr.substring(0, index);

        styledText.add(new Pair<>(processed, style));

        return currentStr.substring(index);
    }

    @Inject(method = "updateCommandInfo", at = @At("HEAD"), cancellable = true)
    public void injectRefresh(CallbackInfo ci) {
        parseCache.clear();

        // Direct tab-complete for altoclef commands (works even when shredder is noop)
        String prefix = this.textField.getValue().substring(0, Math.min(this.textField.getValue().length(), this.textField.getCursorPosition()));
        CommandExecutor executor = AltoClef.getCommandExecutor();
        if (executor == null || !executor.isClientCommand(prefix)) {
            return;
        }

        String[] completions = TabCompleter.complete(prefix);
        if (completions == null) {
            return;
        }

        ci.cancel();
        this.currentParse = null;

        if (this.keepSuggestions) {
            return;
        }

        this.textField.setSuggestion(null);
        this.suggestions = null;
        this.messages.clear();

        if (completions.length == 0) {
            this.pendingSuggestions = Suggestions.empty();
        } else {
            StringRange range = StringRange.between(prefix.lastIndexOf(" ") + 1, prefix.length());
            java.util.List<Suggestion> suggestionList = Stream.of(completions)
                    .map(s -> new Suggestion(range, s))
                    .collect(Collectors.toList());
            Suggestions suggestions = new Suggestions(range, suggestionList);
            this.pendingSuggestions = new CompletableFuture<>();
            this.pendingSuggestions.complete(suggestions);
        }
        ((CommandSuggestions) (Object) this).showSuggestions(true);
    }

    @Inject(method = "formatChat", at = @At("HEAD"), cancellable = true)
    public void inj(String original, int firstCharacterIndex, CallbackInfoReturnable<FormattedCharSequence> cir) {
        String full = this.textField.getValue();

        if (!full.startsWith(AltoClef.getCommandExecutor().getCommandPrefix())) return;

        Pair<String, Integer> key = new Pair<>(original, firstCharacterIndex);

        Pair<MutableComponent, Optional<Pair<MutableComponent, Integer>>> result;
        if (parseCache.containsKey(key)) {
            result = parseCache.get(key);
        } else {
            result = highlightText(original, firstCharacterIndex, full);
            parseCache.put(key, result);
        }

        if (result == null) return;

        messages.clear();
        if (result.getRight().isPresent()) {
            MutableComponent text = result.getRight().get().getLeft();
            int severity = result.getRight().get().getRight();

            messages.add(text.getVisualOrderText());

            if (severity == 1) {
                this.commandUsagePosition = Mth.clamp(this.textField.getScreenX(original.length()), 0, this.textField.getScreenX(0) + this.textField.getInnerWidth());
                this.commandUsageWidth = this.textRenderer.width(text.getString());
            } else if (severity == 2) {
                this.commandUsageWidth = this.owner.width;
                this.commandUsagePosition = 0;
            }
        }
        cir.setReturnValue(result.getLeft().getVisualOrderText());
    }

    @Unique
    private Pair<MutableComponent, Optional<Pair<MutableComponent, Integer>>> highlightText(String original, int firstCharacterIndex, String full) {
        MutableComponent text = Component.empty();
        MutableComponent errorMsg = null;

        Style splitColor = SEMICOLOMN_STYLE;
        int errorSeverity = 0;
        try {
            List<Pair<String, Style>> styledText = new ArrayList<>();

            String[] split = full.split(";", -1);
            int index = 0;
            for (int i = 0; i < split.length; i++) {
                String command = split[i];
                // ⛔ FIXED 2026-09-05: `index` summed only the segment lengths, never the ";"
                // separators consumed between them, so it under-counted by `i` characters once
                // more than one command was chained (";stop ;goto ..."). It is passed straight
                // into buildErrorMessage(msg, full, index) below with `full` (the WHOLE original
                // string, semicolons included) -- so the reported caret position drifted left by
                // one character per prior command in the chain. Same shape as tungsten's
                // split("|") bugs this session: a splitter's pieces silently disagree with the
                // original string's real offsets.
                if (i > 0) index += 1; // the ";" that separated this segment from the last
                index += command.length();

                if (command.endsWith(" ") && (i+1) < split.length) {
                    errorSeverity = 2;
                    errorMsg = buildErrorMessage("Unexpected argument", full, index);
                } else if (command.isBlank()) {
                    errorSeverity = Math.max(errorSeverity, 1);
                }

                if (errorSeverity > 0) {
                    splitColor = this.ERROR_STYLE;

                    styledText.add(new Pair<>(command, this.ERROR_STYLE));
                    if (i + 1 < split.length) {
                        styledText.add(new Pair<>(";", splitColor));
                    }

                    continue;
                }


                Pair<List<Pair<String, Style>>, Pair<Integer, MutableComponent>> part = getText(
                        command.stripLeading(), original.length() + firstCharacterIndex, i + 1 < split.length
                );

                errorSeverity = part.getRight().getLeft();
                if (errorSeverity > 0) {
                    splitColor = this.ERROR_STYLE;
                    errorMsg = part.getRight().getRight();
                }

                List<Pair<String, Style>> styled = new ArrayList<>(part.getLeft());
                String leadingSpace = command.substring(0, command.length() - command.stripLeading().length());

                String first = styled.getFirst().getLeft();
                styled.set(0, new Pair<>(leadingSpace + first, styled.getFirst().getRight()));

                styledText.addAll(styled);

                if (i + 1 < split.length) {
                    styledText.add(new Pair<>(";", splitColor));
                }

            }

            int maxLen = firstCharacterIndex + original.length();

            int length = 0;

            for (Pair<String, Style> pair : styledText) {
                String str = pair.getLeft();

                int nextLength = length + str.length();

                if (nextLength <= firstCharacterIndex) {
                    length = nextLength;
                    continue;
                }

                int start = Math.max(firstCharacterIndex - length, 0);
                int end = Math.min(str.length(), maxLen - length + start);

                String segment = str.substring(start, end);
                text.append(Component.literal(segment).setStyle(pair.getRight()));

                if (length + end >= maxLen) break;

                length = nextLength;
            }

        } catch (CommandException e) {
            return null;
        }
        if (errorMsg != null) {
            return new Pair<>(text, Optional.of(new Pair<>(errorMsg, errorSeverity)));
        }
        return new Pair<>(text, Optional.empty());
    }

    @Unique
    private Pair<List<Pair<String, Style>>, Pair<Integer, MutableComponent>> getText(String s, int maxLen, boolean showUnfinishedErrors) throws CommandException {
        CommandExecutor executor = AltoClef.getCommandExecutor();
        StringReader reader = new StringReader(s);
        String original = s;
        MutableComponent errorMsg = null;

        if (s.isBlank() || reader.peek().isEmpty())
            return new Pair<>(List.of(new Pair<>(s, this.INFO_STYLE)), new Pair<>(0, null));

        String cmd = reader.next();
        boolean hasPrefix = false;
        if (cmd.startsWith(executor.getCommandPrefix())) {
            hasPrefix = true;
            cmd = cmd.substring(executor.getCommandPrefix().length());
        }

        Command command = executor.get(cmd);

        if (command == null) {
            MutableComponent error = Component.literal("Unknown command '" + cmd + "'");

            ArrayList<Pair<String, Style>> res = new ArrayList<>();
            if (hasPrefix) {
                res.add(new Pair<>(executor.getCommandPrefix(), this.INFO_STYLE));
                res.add(new Pair<>(s.substring(executor.getCommandPrefix().length()), this.ERROR_STYLE));
            } else {
                res.add(new Pair<>(s, this.ERROR_STYLE));
            }

            return new Pair<>(res, new Pair<>(2, error));
        }


        List<Pair<String, Style>> styledText = new ArrayList<>();

        s = addStyledText(styledText, original, s, this.INFO_STYLE, reader);

        Arg<?>[] args = command.getArgs();
        int styleIndex = 0;
        int errorSeverity = 0;

        for (int i = 0; i < args.length; i++) {
            Arg<?> arg = args[i];
            if (!reader.hasNext()) {
                if (!arg.hasDefault) {
                    errorMsg = buildErrorMessage("Expected " + arg.getTypeName(), original + " ", original.length() + 1);
                    errorSeverity = 2;
                }
                break;
            }
            Arg.ParseResult result = arg.consumeIfSupplied(reader);

            if (result == Arg.ParseResult.CONSUMED) {
                s = addStyledText(styledText, original, s, this.HIGHLIGHT_STYLES.get(styleIndex), reader);

                styleIndex++;

                if (styleIndex >= this.HIGHLIGHT_STYLES.size()) {
                    styleIndex = 0;
                }

                continue;
            }

            StringReader copy = reader.copy();
            try {
                arg.parseArg(copy);
            } catch (CommandNotFinishedException e) {
                if (showUnfinishedErrors) {
                    errorMsg = buildErrorMessage(e.getMessage(), original, copy.getIndex());
                    errorSeverity = 2;
                } else if ((original.endsWith(" ") || original.endsWith("[") || original.endsWith(",") || original.endsWith(";") || arg instanceof ListArg<?>)
                        && original.length() == maxLen
                ) {
                    String str = command.getHelpRepresentation(cmd, i);
                    errorMsg = Component.literal(str).setStyle(this.INFO_STYLE);

                    errorSeverity = 1;
                }

            } catch (BadCommandSyntaxException e) {
                errorMsg = buildErrorMessage(e.getMessage(), original, copy.getIndex());
                errorSeverity = 2;
            }

            styledText.add(new Pair<>(s, this.ERROR_STYLE));
            s = "";
            break;
        }

        if (!s.isEmpty() || original.endsWith(" ")) {
            styledText.add(new Pair<>(s, this.ERROR_STYLE));

            if (errorMsg == null) {
                errorMsg = buildErrorMessage("Unexpected argument", original, reader.getIndex());
            }
            errorSeverity = 2;
        }

        return new Pair<>(styledText, new Pair<>(errorSeverity, errorMsg));
    }

    @Unique
    private MutableComponent buildErrorMessage(String message, String original, int index) {
        String substr = original.substring(0, index);

        int ind = substr.lastIndexOf(" ");
        if (ind == -1) {
            ind = substr.length();
        }
        substr = substr.substring(0, ind);

        int maxLen = 15;
        if (substr.length() > maxLen) {
            substr = "..." + substr.substring(substr.length() - (maxLen - 3));
        }

        return
                Component.literal(message)
                        .append(Component.literal(" at position " + index + ": " + substr + " <--[HERE]"));
    }

}
