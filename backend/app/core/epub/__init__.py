"""EPUB processing package."""

from .parser_v2 import (
    EPUBParserV2,
    ParserConfig,
    DEFAULT_CONFIG,
    XHTML_NS,
    XHTML_NSMAP,
    OPF_NS,
    DC_NS,
)

# Backward compatibility alias
EPUBParser = EPUBParserV2

__all__ = [
    "EPUBParser",
    "EPUBParserV2",
    "ParserConfig",
    "DEFAULT_CONFIG",
    "XHTML_NS",
    "XHTML_NSMAP",
    "OPF_NS",
    "DC_NS",
]

