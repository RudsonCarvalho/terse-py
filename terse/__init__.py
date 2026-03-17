"""TERSE – Token-Efficient Recursive Serialization Encoding."""
from .core import serialize, parse, serialize_document, parse_document, TerseError

__all__ = ["serialize", "parse", "serialize_document", "parse_document", "TerseError"]
__version__ = "0.1.0"
