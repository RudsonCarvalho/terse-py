"""
TERSE v0.7 – parser and serializer.

Public API
----------
serialize(val) -> str          # single value → TERSE string
parse(src) -> Any              # TERSE string → Python value
serialize_document(obj) -> str # dict → top-level key-value document
parse_document(src) -> dict    # top-level key-value document → dict
"""
from __future__ import annotations

import math
import re
from typing import Any

# ─── Error ───────────────────────────────────────────────────────────────────


class TerseError(ValueError):
    """Raised for parse and serialization errors."""

    def __init__(self, message: str, position: int = -1, code: str = "PARSE_ERROR"):
        super().__init__(message)
        self.position = position
        self.code = code


# ─── Grammar constants ────────────────────────────────────────────────────────

MAX_DEPTH = 64
LINE_LIMIT = 80

# §3.5 safe-id
_SAFE_START = re.compile(r"[A-Za-z_./]")
_SAFE_ID = re.compile(r"[A-Za-z_./][A-Za-z0-9\-_./@]*")
# §4.3 number (JSON subset)
_NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_RESERVED = {"T", "F", "~", "{}", "[]"}
_NUMBER_FULL = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")


def _is_safe_id(s: str) -> bool:
    if not _SAFE_ID.fullmatch(s):
        return False
    if s in _RESERVED:
        return False
    if _NUMBER_FULL.match(s):
        return False
    return True


# ─── Serializer ───────────────────────────────────────────────────────────────

def _serialize_string(s: str) -> str:
    if _is_safe_id(s):
        return s
    # JSON-compatible quoting
    escaped = (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("\n", "\\n")
         .replace("\r", "\\r")
         .replace("\t", "\\t")
         .replace("\b", "\\b")
         .replace("\f", "\\f")
    )
    return f'"{escaped}"'


def _serialize_key(k: str) -> str:
    return _serialize_string(k)


def _schema_keys(arr: list) -> list[str] | None:
    """Return shared key list if arr qualifies for schema-array form, else None."""
    if len(arr) < 2:
        return None
    if not all(isinstance(v, dict) and not isinstance(v, list) for v in arr):
        return None
    keys = list(arr[0].keys())
    if not keys:
        return None
    for obj in arr:
        if list(obj.keys()) != keys:
            return None
        if not all(_is_primitive(v) for v in obj.values()):
            return None
    return keys


def _is_primitive(v: Any) -> bool:
    return v is None or isinstance(v, (bool, int, float, str))


def _serialize_primitive(v: Any) -> str:
    if v is None:
        return "~"
    if isinstance(v, bool):
        return "T" if v else "F"
    if isinstance(v, (int, float)):
        return _serialize_number(v)
    return _serialize_string(v)


def _serialize_number(n: float | int) -> str:
    if isinstance(n, float) and not math.isfinite(n):
        raise TerseError(f"Cannot serialize non-finite number: {n}", -1, "INVALID_VALUE")
    if isinstance(n, bool):
        raise TerseError("Use boolean serialization for bool values", -1, "INVALID_TYPE")
    # Produce shortest round-trippable representation
    if isinstance(n, int):
        return str(n)
    # Float: use repr for round-trip precision, but remove trailing zeros
    s = repr(n)
    return s


def _try_inline(val: Any, depth: int = 0) -> str | None:
    if depth > MAX_DEPTH:
        return None
    if val is None:
        return "~"
    if isinstance(val, bool):
        return "T" if val else "F"
    if isinstance(val, (int, float)):
        if isinstance(val, float) and not math.isfinite(val):
            return None
        return _serialize_number(val)
    if isinstance(val, str):
        return _serialize_string(val)
    if isinstance(val, list):
        if not val:
            return "[]"
        if _schema_keys(val) is not None:
            return None  # always block
        parts = [_try_inline(v, depth + 1) for v in val]
        if any(p is None for p in parts):
            return None
        return "[" + " ".join(parts) + "]"  # type: ignore[arg-type]
    if isinstance(val, dict):
        if not val:
            return "{}"
        parts = []
        for k, v in val.items():
            vi = _try_inline(v, depth + 1)
            if vi is None:
                return None
            parts.append(f"{_serialize_key(k)}:{vi}")
        return "{" + " ".join(parts) + "}"
    return None


def serialize(val: Any, _depth: int = 0) -> str:
    """Serialize any Python value to a TERSE string (value-level)."""
    if _depth > MAX_DEPTH:
        raise TerseError("Maximum nesting depth exceeded", -1, "MAX_DEPTH_EXCEEDED")

    if val is None:
        return "~"
    if isinstance(val, bool):
        return "T" if val else "F"
    if isinstance(val, (int, float)):
        if isinstance(val, float) and not math.isfinite(val):
            raise TerseError(f"Cannot serialize non-finite number: {val}", -1, "INVALID_VALUE")
        return _serialize_number(val)
    if isinstance(val, str):
        return _serialize_string(val)

    if isinstance(val, list):
        if not val:
            return "[]"
        sk = _schema_keys(val)
        if sk is not None:
            return _serialize_schema_array(val, sk, _depth)
        inline = _try_inline(val, _depth)
        if inline is not None and len(inline) <= LINE_LIMIT:
            return inline
        ind = "  " * (_depth + 1)
        items = [f"{ind}{serialize(v, _depth + 1)}" for v in val]
        close_ind = "  " * _depth
        return "[\n" + "\n".join(items) + f"\n{close_ind}]"

    if isinstance(val, dict):
        if not val:
            return "{}"
        inline = _try_inline(val, _depth)
        if inline is not None and len(inline) <= LINE_LIMIT:
            return inline
        ind = "  " * (_depth + 1)
        lines = [f"{ind}{_serialize_key(k)}:{serialize(v, _depth + 1)}" for k, v in val.items()]
        close_ind = "  " * _depth
        return "{\n" + "\n".join(lines) + f"\n{close_ind}}}"

    raise TerseError(f"Cannot serialize value of type {type(val).__name__}", -1, "INVALID_TYPE")


def _serialize_schema_array(arr: list, keys: list[str], depth: int) -> str:
    ind = "  " * (depth + 1)
    header = "#[" + " ".join(_serialize_key(k) for k in keys) + "]"
    rows = []
    for obj in arr:
        vals = [_serialize_primitive(obj[k]) for k in keys]
        rows.append(f"{ind}" + " ".join(vals))
    return header + "\n" + "\n".join(rows)


def serialize_document(obj: dict) -> str:
    """Serialize a dict as a TERSE document (top-level key-value pairs, no outer braces)."""
    lines = []
    for k, v in obj.items():
        key = _serialize_key(k)
        # Schema arrays
        if isinstance(v, list):
            sk = _schema_keys(v)
            if sk is not None:
                schema_str = _serialize_schema_array(v, sk, 0)
                lines.append(f"{key}:\n  {schema_str}")
                continue
        inline = _try_inline(v)
        if inline is not None and (len(key) + 2 + len(inline)) <= LINE_LIMIT:
            lines.append(f"{key}:{inline}")
        else:
            block = serialize(v, 1)
            lines.append(f"{key}:\n  {block}")
    return "\n".join(lines) + ("\n" if lines else "")


# ─── Parser ───────────────────────────────────────────────────────────────────


class _Parser:
    def __init__(self, src: str):
        if "\t" in src:
            pos = src.index("\t")
            raise TerseError(
                f"Tab character (U+0009) is not allowed in TERSE at position {pos}",
                pos,
                "ILLEGAL_CHARACTER",
            )
        self.src = src
        self.pos = 0
        self.depth = 0

    # ── helpers ────────────────────────────────────────────────────────────────

    def _is_kv_start(self) -> bool:
        """Return True if current position starts a key:value pair."""
        saved = self.pos
        try:
            if self.cur() == '"':
                self.parse_quoted_string()
            elif _SAFE_START.match(self.cur()):
                m = _SAFE_ID.match(self.src, self.pos)
                if not m:
                    return False
                self.pos = m.end()
            else:
                return False
            self.skip_hws()
            return self.cur() == ':'
        except Exception:
            return False
        finally:
            self.pos = saved

    def cur(self) -> str:
        return self.src[self.pos] if self.pos < len(self.src) else ""

    def peek(self, n: int = 1) -> str:
        i = self.pos + n
        return self.src[i] if i < len(self.src) else ""

    def eof(self) -> bool:
        return self.pos >= len(self.src)

    def skip_hws(self) -> None:
        while self.pos < len(self.src) and self.src[self.pos] == " ":
            self.pos += 1

    def skip_ws_lines(self) -> None:
        while not self.eof():
            ch = self.src[self.pos]
            if ch in (" ", "\n", "\r"):
                self.pos += 1
            elif ch == "/" and self.peek() == "/":
                while not self.eof() and self.src[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def expect(self, ch: str) -> None:
        if self.cur() != ch:
            got = repr(self.cur()) if self.cur() else "EOF"
            raise TerseError(
                f"Expected {repr(ch)} at position {self.pos}, got {got}",
                self.pos,
                "UNEXPECTED_CHARACTER",
            )
        self.pos += 1

    # ── number ─────────────────────────────────────────────────────────────────

    def parse_number(self) -> int | float:
        m = _NUMBER.match(self.src, self.pos)
        if not m:
            raise TerseError(f"Expected number at {self.pos}", self.pos, "UNEXPECTED_CHARACTER")
        self.pos = m.end()
        s = m.group()
        return int(s) if "." not in s and "e" not in s.lower() else float(s)

    # ── quoted string ──────────────────────────────────────────────────────────

    def parse_quoted_string(self) -> str:
        start = self.pos
        self.pos += 1  # skip opening "
        r: list[str] = []
        while self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch == '"':
                self.pos += 1
                return "".join(r)
            if ch == "\\":
                self.pos += 1
                esc = self.src[self.pos] if self.pos < len(self.src) else ""
                simple = {"\"": '"', "\\": "\\", "n": "\n", "r": "\r",
                          "t": "\t", "b": "\b", "f": "\f"}
                if esc in simple:
                    r.append(simple[esc])
                elif esc == "u":
                    hex4 = self.src[self.pos + 1: self.pos + 5]
                    if not re.fullmatch(r"[0-9A-Fa-f]{4}", hex4):
                        raise TerseError(
                            f"Invalid \\u escape at {self.pos}", self.pos, "INVALID_ESCAPE")
                    r.append(chr(int(hex4, 16)))
                    self.pos += 4
                else:
                    raise TerseError(
                        f"Invalid escape '\\{esc}' at {self.pos}", self.pos, "INVALID_ESCAPE")
                self.pos += 1
            else:
                r.append(ch)
                self.pos += 1
        raise TerseError(f"Unterminated string at {start}", start, "UNTERMINATED_STRING")

    # ── safe-id ────────────────────────────────────────────────────────────────

    def parse_safe_id(self) -> str:
        m = _SAFE_ID.match(self.src, self.pos)
        if not m:
            raise TerseError(
                f"Expected identifier at {self.pos}, got {repr(self.cur())}",
                self.pos, "EXPECTED_KEY")
        self.pos = m.end()
        return m.group()

    def parse_key(self) -> str:
        return self.parse_quoted_string() if self.cur() == '"' else self.parse_safe_id()

    # ── primitive (schema-array rows) ─────────────────────────────────────────

    def parse_primitive(self) -> Any:
        ch = self.cur()
        if ch == "~":
            self.pos += 1
            return None
        if ch == '"':
            return self.parse_quoted_string()
        if ch == "-" or ch.isdigit():
            return self.parse_number()
        if _SAFE_START.match(ch):
            ident = self.parse_safe_id()
            if ident == "T":
                return True
            if ident == "F":
                return False
            return ident
        raise TerseError(
            f"Expected primitive at {self.pos}", self.pos, "UNEXPECTED_CHARACTER")

    # ── value ──────────────────────────────────────────────────────────────────

    def parse_value(self) -> Any:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise TerseError("Maximum nesting depth (64) exceeded", self.pos, "MAX_DEPTH_EXCEEDED")
        try:
            self.skip_hws()
            ch = self.cur()
            if not ch:
                raise TerseError("Unexpected end of input", self.pos, "UNEXPECTED_EOF")
            if ch == "~":
                self.pos += 1
                return None
            if ch == '"':
                return self.parse_quoted_string()
            if ch == "{":
                return self.parse_object()
            if ch == "[":
                return self.parse_array()
            if ch == "#":
                return self.parse_schema_array()
            if ch == "-" or ch.isdigit():
                return self.parse_number()
            if _SAFE_START.match(ch):
                ident = self.parse_safe_id()
                if ident == "T":
                    return True
                if ident == "F":
                    return False
                return ident
            raise TerseError(
                f"Unexpected character {repr(ch)} at position {self.pos}",
                self.pos, "UNEXPECTED_CHARACTER")
        finally:
            self.depth -= 1

    # ── object ─────────────────────────────────────────────────────────────────

    def parse_object(self) -> dict:
        start = self.pos
        self.pos += 1  # skip {
        obj: dict = {}

        self.skip_hws()
        is_block = self.cur() in ("\n", "\r")

        while not self.eof():
            if is_block:
                self.skip_ws_lines()
            else:
                self.skip_hws()
            if self.cur() == "}":
                break
            if self.eof():
                raise TerseError(f"Unterminated object at {start}", start, "UNTERMINATED_OBJECT")

            key = self.parse_key()
            self.skip_hws()
            self.expect(":")
            self.skip_hws()
            if is_block and self.cur() in ("\n", "\r"):
                self.skip_ws_lines()

            val = self.parse_value()

            if key in obj:
                raise TerseError(
                    f"Duplicate key '{key}' at {self.pos}", self.pos, "DUPLICATE_KEY")
            obj[key] = val

            if not is_block:
                self.skip_hws()
            else:
                self.skip_hws()
                if self.cur() not in ("}", "\n", "\r") and not self.eof():
                    raise TerseError(
                        f"Expected newline after value at {self.pos}", self.pos, "EXPECTED_NEWLINE")

        if self.cur() != "}":
            raise TerseError(f"Unterminated object at {start}", start, "UNTERMINATED_OBJECT")
        self.pos += 1
        return obj

    # ── array ──────────────────────────────────────────────────────────────────

    def parse_array(self) -> list:
        start = self.pos
        self.pos += 1  # skip [
        items: list = []

        self.skip_hws()
        is_block = self.cur() in ("\n", "\r")

        while not self.eof():
            if is_block:
                self.skip_ws_lines()
            else:
                self.skip_hws()
            if self.cur() == "]":
                break
            if self.eof():
                raise TerseError(f"Unterminated array at {start}", start, "UNTERMINATED_ARRAY")

            items.append(self.parse_value())

            if not is_block:
                self.skip_hws()
            else:
                self.skip_hws()
                if self.cur() not in ("]", "\n", "\r") and not self.eof():
                    raise TerseError(
                        f"Expected newline after value at {self.pos}", self.pos, "EXPECTED_NEWLINE")

        if self.cur() != "]":
            raise TerseError(f"Unterminated array at {start}", start, "UNTERMINATED_ARRAY")
        self.pos += 1
        return items

    # ── schema array ───────────────────────────────────────────────────────────

    def parse_schema_array(self) -> list[dict]:
        start = self.pos
        self.expect("#")
        self.expect("[")

        fields: list[str] = []
        self.skip_hws()
        while not self.eof() and self.cur() != "]":
            fields.append(self.parse_key())
            self.skip_hws()
        self.expect("]")

        if not fields:
            raise TerseError("Schema header must have at least one field", start, "EXPECTED_KEY")

        rows: list[dict] = []

        while not self.eof():
            if self.cur() not in ("\n", "\r"):
                break
            line_start = self.pos  # save position before consuming newline+indent
            # peek ahead to check indentation
            pi = self.pos
            while pi < len(self.src) and self.src[pi] in ("\n", "\r"):
                pi += 1
            spaces = 0
            while pi + spaces < len(self.src) and self.src[pi + spaces] == " ":
                spaces += 1
            if spaces < 2:
                break

            # consume newlines + indentation
            while self.cur() in ("\n", "\r"):
                self.pos += 1
            self.skip_hws()

            # blank or comment line
            if self.cur() in ("\n", "\r"):
                continue
            if self.cur() == "/" and self.peek() == "/":
                while not self.eof() and self.cur() != "\n":
                    self.pos += 1
                continue

            # Stop if this line is a KV pair (key followed by ':') — not a data row
            if self._is_kv_start():
                self.pos = line_start  # restore to \n before this line
                break

            row: dict = {}
            for i, field in enumerate(fields):
                if i > 0:
                    self.expect(" ")
                row[field] = self.parse_primitive()

            self.skip_hws()
            if self.cur() not in ("\n", "\r") and not self.eof():
                raise TerseError(
                    f"Schema row has too many values at {self.pos}",
                    self.pos, "SCHEMA_WRONG_COLUMNS")
            rows.append(row)

        return rows


class _DocumentParser:
    def __init__(self, src: str):
        self._p = _Parser(src)

    def parse(self) -> dict:
        p = self._p
        doc: dict = {}
        p.skip_ws_lines()

        while not p.eof():
            key = p.parse_key()
            p.skip_hws()
            p.expect(":")
            p.skip_hws()

            if p.cur() in ("\n", "\r"):
                while p.cur() in ("\n", "\r"):
                    p.pos += 1
                p.skip_hws()
                val = p.parse_value()
            else:
                val = p.parse_value()

            if key in doc:
                raise TerseError(
                    f"Duplicate key '{key}' at {p.pos}", p.pos, "DUPLICATE_KEY")
            doc[key] = val
            p.skip_ws_lines()

        return doc


# ─── Public API ───────────────────────────────────────────────────────────────


def parse(src: str) -> Any:
    """Parse a single TERSE value."""
    p = _Parser(src)
    p.skip_ws_lines()
    val = p.parse_value()
    p.skip_ws_lines()
    if not p.eof():
        raise TerseError(
            f"Unexpected content at position {p.pos}", p.pos, "UNEXPECTED_CONTENT")
    return val


def parse_document(src: str) -> dict:
    """Parse a TERSE document into a dict."""
    return _DocumentParser(src).parse()
