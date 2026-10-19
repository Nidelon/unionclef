#!/usr/bin/env python3
"""Shared parser for javac error output.

javac prints, for a "cannot find symbol":

  /path/File.java:123: error: cannot find symbol
          foo.bar();
             ^
    symbol:   method bar()
    location: class Foo

The caret column is what makes an error-driven rename safe: it points at the
exact identifier that failed, so a fixer can rewrite that one token instead of
guessing at every occurrence of the name in the file.
"""
import re
from dataclasses import dataclass, field

HEADER_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<file>.+?):(?P<line>\d+): error: (?P<msg>.*)$")
CARET_RE = re.compile(r"^\s*\^+\s*$")
SYMBOL_RE = re.compile(r"^\s*symbol:\s+(?P<rest>.*\S)\s*$")
LOCATION_RE = re.compile(r"^\s*location:\s+(?P<rest>.*\S)\s*$")
TYPE_OF_RE = re.compile(r"of type\s+(?P<type>[^\s]+)")


@dataclass
class Record:
    file: str
    line: int
    msg: str
    col: int | None = None
    source_line: str | None = None
    sym_raw: str | None = None
    loc_raw: str | None = None
    sym_kind: str | None = None
    sym_name: str | None = None
    loc_kind: str | None = None
    loc_name: str | None = None
    extra: dict = field(default_factory=dict)

    def finalize(self):
        if self.sym_raw:
            parts = self.sym_raw.split(None, 1)
            if parts and parts[0] in ("method", "variable", "class", "interface",
                                      "constructor", "enum", "record"):
                self.sym_kind = parts[0]
                name = parts[1] if len(parts) > 1 else ""
            else:
                self.sym_kind = "class"
                name = self.sym_raw
            name = name.strip()
            # `bar()` -> bar ; `bar(int,String)` -> bar ; `Bar` -> Bar
            self.sym_name = re.split(r"[(\s]", name, 1)[0].strip()
        if self.loc_raw:
            parts = self.loc_raw.split(None, 1)
            if parts and parts[0] in ("class", "interface", "enum", "record",
                                      "variable", "package", "constructor"):
                self.loc_kind = parts[0]
                rest = parts[1] if len(parts) > 1 else ""
            else:
                self.loc_kind = "class"
                rest = self.loc_raw
            if self.loc_kind == "variable":
                m = TYPE_OF_RE.search(rest)
                if m:
                    self.loc_name = m.group("type").split("<")[0].strip()
                else:
                    self.loc_name = None
            else:
                self.loc_name = rest.split("<")[0].strip().rstrip(".")


def parse_log(path):
    """Parse javac output.

    javac switches to a compact style after a multi-line diagnostic: the
    following errors are printed with a two-space indent, and their source line
    and caret carry the same indent. Both are normalised away here, otherwise
    half the records point at paths that do not exist.
    """
    records = []
    cur = None
    prev_line = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = HEADER_RE.match(line)
            if m:
                if cur:
                    cur.finalize()
                    records.append(cur)
                indent = len(m.group("indent"))
                cur = Record(file=m.group("file").strip(),
                             line=int(m.group("line")),
                             msg=m.group("msg"))
                cur.extra["indent"] = indent
                prev_line = None
                continue
            if cur is None:
                continue
            indent = cur.extra.get("indent", 0)
            if CARET_RE.match(line):
                if prev_line is not None and cur.col is None:
                    src = prev_line
                    if indent and src[:indent].strip() == "":
                        src = src[indent:]
                    cur.source_line = src
                    cur.col = max(0, line.index("^") - indent)
                prev_line = None
                continue
            sm = SYMBOL_RE.match(line)
            if sm and cur.sym_raw is None:
                cur.sym_raw = sm.group("rest")
                prev_line = None
                continue
            lm = LOCATION_RE.match(line)
            if lm and cur.loc_raw is None:
                cur.loc_raw = lm.group("rest")
                prev_line = None
                continue
            if line.strip():
                prev_line = line
    if cur:
        cur.finalize()
        records.append(cur)
    return records
