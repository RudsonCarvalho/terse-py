# terse-py

[![CI](https://github.com/RudsonCarvalho/terse-py/actions/workflows/ci.yml/badge.svg)](https://github.com/RudsonCarvalho/terse-py/actions/workflows/ci.yml)

Python implementation of the [TERSE](https://github.com/RudsonCarvalho/terse-format) format.

**TERSE** (Token-Efficient Recursive Serialization Encoding) is a compact, LLM-native alternative to JSON with **30–55% fewer tokens**.

## Installation

```bash
pip install terse-py
```

## Usage

```python
from terse import serialize, parse, serialize_document, parse_document

# Serialize values
serialize(None)                   # "~"
serialize(True)                   # "T"
serialize(42)                     # "42"
serialize("hello")                # "hello"
serialize("T")                    # '"T"'  (quoted — literal T)
serialize({"a": 1, "b": "hi"})   # "{a:1 b:hi}"

# Uniform list of dicts → schema array (token-efficient)
serialize([
    {"id": 1, "name": "Alice", "active": True},
    {"id": 2, "name": "Bob",   "active": False},
])
# "#[id name active]\n  1 Alice T\n  2 Bob F"

# Parse values
parse("~")                    # None
parse("T")                    # True
parse("{name:Alice age:30}")  # {"name": "Alice", "age": 30}
parse("[1 2 3]")              # [1, 2, 3]

# Document API
src = """
name: my-app
version: "2.1.0"
private: T
"""
parse_document(src)
# {"name": "my-app", "version": "2.1.0", "private": True}
```

## API

| Function | Description |
|---|---|
| `serialize(val)` | Serialize any Python value to TERSE |
| `parse(src)` | Parse a TERSE value string |
| `serialize_document(obj)` | Serialize a dict as a TERSE document |
| `parse_document(src)` | Parse a TERSE document into a dict |

See the [TERSE spec](https://github.com/RudsonCarvalho/terse-format) for the full grammar.

## License

MIT
