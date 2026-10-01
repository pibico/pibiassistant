# pibiAssistant - Services Module
# Copyright (C) 2025 Paul Clinton

"""
Services module for pibiAssistant

SSE Bridge has been deprecated and removed.
Use StreamableHTTP (OAuth-based) transport instead.
"""

# Import version from parent module
try:
    from pibiassistant import __version__
except ImportError:
    __version__ = "unknown"
