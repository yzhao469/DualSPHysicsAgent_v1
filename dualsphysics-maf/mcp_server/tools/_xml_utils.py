"""Shared XML utilities for DualSPHysics case files.

The base XML uses a few non-standard features (triple-dash comments, unescaped
< and > inside attribute values) that standard parsers reject.  We fix them
in memory before parsing, then write clean XML back.
"""
import re


def preprocess_xml(content: str) -> str:
    """Fix non-standard XML features used in DualSPHysics case files.

    Handles:
    - Triple-dash XML comments: <!---...--->  ->  <!-- ... -->
    - Unescaped < and > inside quoted attribute values
    - Percent-sign inline comments (e.g. ``%text`` outside tags)
    """
    # Fix triple-dash comments
    content = re.sub(
        r'<!---+(.*?)-+-->',
        lambda m: '<!-- ' + re.sub(r'-{2,}', '-', m.group(1).strip()) + ' -->',
        content,
        flags=re.DOTALL,
    )

    # Remove %-style inline comments (GenCase extension, not valid XML).
    # Only match % that appears outside of XML tags — specifically, after a
    # tag-close (>) and before end-of-line, not inside attribute values.
    # Pattern: match % that is preceded by > (possibly with whitespace) on the same line.
    content = re.sub(r'(>)\s*%[^\n]*', r'\1', content)
    # Also match %-comments on their own line (not inside any tag)
    content = re.sub(r'^\s*%[^\n]*$', '', content, flags=re.MULTILINE)

    # Fix unescaped < and > inside quoted attribute values
    def _fix_attr(m: re.Match) -> str:
        quote = m.group(1)
        val = m.group(2)
        val = re.sub(r'<', '&lt;', val)
        val = re.sub(r'>', '&gt;', val)
        return f'={quote}{val}{quote}'

    content = re.sub(r'=([\"\'])(.*?)\1', _fix_attr, content, flags=re.DOTALL)
    return content
