import com.sun.source.util.JavacTask;
import com.sun.source.util.TaskEvent;
import com.sun.source.util.TaskListener;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.LineMap;

import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;
import java.io.File;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Emit javac diagnostics as JSON, with exact source offsets.
 *
 * The text output of javac is a poor interface for automated fixing: it wraps
 * long paths, switches to a compact indented style mid-report, and gives only a
 * caret column, so every fixer ends up re-deriving the offending expression from
 * a column guess. Diagnostic.getStartPosition()/getEndPosition() give the real
 * range, and the JavacTask listener gives the LineMap to turn it into line and
 * column.
 *
 * Usage:
 *   java DumpDiagnostics @sources.txt -cp <classpath> -d <outdir> > diag.jsonl
 *
 * One JSON object per line:
 *   {"file":..., "line":..., "col":..., "start":..., "end":...,
 *    "kind":"ERROR", "code":"compiler.err.cant.resolve.location",
 *    "message":"...", "lineText":"..."}
 */
public final class DumpDiagnostics {

    public static void main(String[] args) throws Exception {
        List<String> files = new ArrayList<>();
        List<String> options = new ArrayList<>();
        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            if (a.startsWith("@")) {
                for (String line : Files.readAllLines(Path.of(a.substring(1)), StandardCharsets.UTF_8)) {
                    if (!line.isBlank()) {
                        files.add(line.trim());
                    }
                }
            } else if (a.equals("-cp") || a.equals("-classpath")) {
                options.add(a);
                options.add(args[++i]);
            } else if (a.equals("-d")) {
                options.add(a);
                options.add(args[++i]);
            } else if (a.startsWith("-")) {
                options.add(a);
            } else {
                files.add(a);
            }
        }
        options.add("-Xmaxerrs");
        options.add("1000000");
        options.add("-Xlint:none");
        options.add("-proc:none");
        options.add("-nowarn");

        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        DiagnosticCollector<JavaFileObject> collector = new DiagnosticCollector<>();
        StandardJavaFileManager fm = compiler.getStandardFileManager(collector, null, StandardCharsets.UTF_8);
        Iterable<? extends JavaFileObject> units = fm.getJavaFileObjectsFromStrings(files);

        JavacTask task = (JavacTask) compiler.getTask(
                new PrintWriter(System.err), fm, collector, options, null, units);

        Map<JavaFileObject, LineMap> lineMaps = new HashMap<>();
        Map<JavaFileObject, List<String>> sourceLines = new HashMap<>();

        task.addTaskListener(new TaskListener() {
            @Override
            public void finished(TaskEvent e) {
                if (e.getKind() == TaskEvent.Kind.PARSE && e.getCompilationUnit() != null) {
                    CompilationUnitTree unit = e.getCompilationUnit();
                    lineMaps.put(unit.getSourceFile(), unit.getLineMap());
                    try {
                        sourceLines.put(unit.getSourceFile(),
                                Files.readAllLines(Path.of(unit.getSourceFile().toUri()),
                                        StandardCharsets.UTF_8));
                    } catch (Exception ignored) {
                        // source text is a convenience, not a requirement
                    }
                }
            }
        });

        try {
            task.call();
        } catch (Exception e) {
            System.err.println("compilation aborted: " + e);
        }

        StringBuilder out = new StringBuilder();
        for (Diagnostic<? extends JavaFileObject> d : collector.getDiagnostics()) {
            if (d.getKind() != Diagnostic.Kind.ERROR) {
                continue;
            }
            JavaFileObject src = d.getSource();
            long line = d.getLineNumber();
            long col = d.getColumnNumber();
            long start = d.getStartPosition();
            long end = d.getEndPosition();
            String lineText = "";
            if (src != null && line > 0) {
                List<String> lines = sourceLines.get(src);
                if (lines != null && line - 1 < lines.size()) {
                    lineText = lines.get((int) (line - 1));
                }
            }
            out.setLength(0);
            out.append('{');
            out.append("\"file\":").append(json(src == null ? "" : new File(src.toUri()).getAbsolutePath())).append(',');
            out.append("\"line\":").append(line).append(',');
            out.append("\"col\":").append(col).append(',');
            out.append("\"start\":").append(start).append(',');
            out.append("\"end\":").append(end).append(',');
            out.append("\"code\":").append(json(d.getCode())).append(',');
            out.append("\"message\":").append(json(d.getMessage(null))).append(',');
            out.append("\"lineText\":").append(json(lineText));
            out.append('}');
            System.out.println(out);
        }
        fm.close();
    }

    private static String json(String s) {
        StringBuilder b = new StringBuilder(s.length() + 16);
        b.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> b.append("\\\"");
                case '\\' -> b.append("\\\\");
                case '\n' -> b.append("\\n");
                case '\r' -> b.append("\\r");
                case '\t' -> b.append("\\t");
                default -> {
                    if (c < 0x20) {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
                }
            }
        }
        b.append('"');
        return b.toString();
    }
}
