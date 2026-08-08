#!/usr/bin/env python3
"""
chat_viewer.py  –  Pretty-print a DualSPHysics agent chat_history.jsonl file.

────────────────────────────────────────────────────────────────
  OPTION A – edit paths directly here (no command-line needed):
────────────────────────────────────────────────────────────────
"""

# ══ HARDCODED PATHS (used when no command-line arguments are given) ══════════
INPUT_FILE  = "Evaluation_post_processing/Archived_run_cases/run_case04_03/chat_history.jsonl"   # ← change to your .jsonl path
OUTPUT_FILE = "Evaluation_post_processing/Archived_run_cases/run_case04_03/conversation.html"     # ← change to desired output path, or set
                                     #   None  to print to terminal
# ════════════════════════════════════════════════════════════════════════════

"""
────────────────────────────────────────────────────────────────
  OPTION B – pass paths on the command line (overrides the above):

    python chat_viewer.py chat_history.jsonl
    python chat_viewer.py chat_history.jsonl --out conversation.html
    python chat_viewer.py chat_history.jsonl --out conversation.txt
    python chat_viewer.py chat_history.jsonl --no-color   (terminal, no color)
────────────────────────────────────────────────────────────────
"""

import json
import re
import argparse
import html as html_lib
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
#  TERMINAL (ANSI) renderer
# ─────────────────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
WHITE  = "\033[97m"

USE_COLOR = True


def c(code, text):
    return f"{code}{text}{RESET}" if USE_COLOR else text


def fmt_ts(ts_str):
    try:
        dt = datetime.fromisoformat(ts_str).astimezone()
        return dt.strftime("%Y-%m-%d  %H:%M:%S")
    except Exception:
        return ts_str


def clean(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


ROLE_FMT_ANSI = {
    "user":      (GREEN, "YOU"),
    "assistant": (CYAN,  "AGENT"),
}


def render_terminal(records, no_color=False):
    global USE_COLOR
    USE_COLOR = not no_color

    def divider(char="─", width=72):
        return c(DIM, char * width)

    lines = []
    lines.append(divider("═"))
    lines.append(c(BOLD + WHITE, f"  CONVERSATION LOG  ·  {len(records)} messages"))
    lines.append(divider("═"))
    lines.append("")

    for rec in records:
        role    = rec.get("role", "unknown")
        ts      = rec.get("ts", "")
        phase   = rec.get("phase", "")
        content = clean(rec.get("content", ""))

        color, label = ROLE_FMT_ANSI.get(role, (WHITE, role.upper()))
        header = (c(BOLD + color, f"[{label}]")
                  + c(DIM, f"  {fmt_ts(ts)}")
                  + (c(DIM + YELLOW, f"  ({phase})") if phase else ""))

        lines.append(header)
        lines.append(divider())
        for cl in content.split("\n"):
            lines.append("  " + cl)
        lines.append("")

    print("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────────────
#  HTML renderer
# ─────────────────────────────────────────────────────────────────────────────
HTML_STYLE = """
:root {
  --bg:        #f5f5f5;
  --surface:   #ffffff;
  --border:    #d0d0d0;
  --user-col:  #1a7a4a;
  --agent-col: #1a5fa0;
  --phase-col: #b36b00;
  --ts-col:    #666888;
  --text:      #1a1a2e;
  --code-bg:   #f0f0f0;
  --dim:       #888888;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Segoe UI', system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  padding: 32px 16px;
}
.log-header {
  text-align: center;
  padding: 18px;
  margin-bottom: 32px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  font-size: 13px;
  color: var(--dim);
  letter-spacing: .05em;
}
.log-header strong { color: var(--text); font-size: 16px; }
.messages { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
.bubble {
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
  overflow: hidden;
}
.bubble-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
}
.role-badge {
  font-weight: 700;
  font-size: 13px;
  padding: 2px 10px;
  border-radius: 20px;
}
.role-user  .role-badge { background: #d4f0e0; color: var(--user-col);  }
.role-agent .role-badge { background: #d0e8f8; color: var(--agent-col); }
.ts    { color: var(--ts-col); }
.phase { color: var(--phase-col); font-style: italic; }
.bubble-body {
  padding: 14px 18px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13.5px;
}
.bubble-body pre {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  overflow-x: auto;
  margin: 8px 0;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 12.5px;
  color: #6a0dad;
  white-space: pre;
}
.sep-line { border: none; border-top: 1px solid var(--border); margin: 8px 0; }
"""


def escape(text):
    return html_lib.escape(text)


def content_to_html(text):
    parts = re.split(r'(```(?:\w*\n)?[\s\S]*?```)', text)
    out = []
    for part in parts:
        if part.startswith("```"):
            body = re.sub(r'^```\w*\n?', '', part)
            body = re.sub(r'```$', '', body)
            out.append(f'<pre>{escape(body.strip())}</pre>')
        else:
            escaped = escape(part)
            escaped = re.sub(r'(?m)^(={4,}|-{4,}|─{4,}|═{4,})$',
                             '<hr class="sep-line">', escaped)
            out.append(escaped)
    return "".join(out)


def render_html(records, input_path, out_path):
    ROLE_META = {
        "user":      ("role-user",  "YOU"),
        "assistant": ("role-agent", "AGENT"),
    }

    bubbles = []
    for rec in records:
        role    = rec.get("role", "unknown")
        ts      = fmt_ts(rec.get("ts", ""))
        phase   = rec.get("phase", "")
        content = clean(rec.get("content", ""))

        css_cls, label = ROLE_META.get(role, ("role-agent", role.upper()))
        phase_html = f'<span class="phase">({escape(phase)})</span>' if phase else ""
        body_html  = content_to_html(content)

        bubbles.append(f"""  <div class="bubble {css_cls}">
    <div class="bubble-header">
      <span class="role-badge">{label}</span>
      <span class="ts">{escape(ts)}</span>
      {phase_html}
    </div>
    <div class="bubble-body">{body_html}</div>
  </div>""")

    n = len(records)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Chat Log – {escape(input_path)}</title>
  <style>{HTML_STYLE}</style>
</head>
<body>
  <div class="log-header">
    <strong>CONVERSATION LOG</strong><br>
    {n} messages &nbsp;·&nbsp; {escape(input_path)}
  </div>
  <div class="messages">
{chr(10).join(bubbles)}
  </div>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved HTML → {out_path}  (open in any browser)")


# ─────────────────────────────────────────────────────────────────────────────
#  Plain-text renderer
# ─────────────────────────────────────────────────────────────────────────────
def render_txt(records, input_path, out_path):
    lines = []
    lines.append("=" * 72)
    lines.append(f"  CONVERSATION LOG  ·  {len(records)} messages  ·  {input_path}")
    lines.append("=" * 72)
    lines.append("")

    ROLE_LABEL = {"user": "YOU", "assistant": "AGENT"}
    for rec in records:
        role    = rec.get("role", "unknown")
        ts      = fmt_ts(rec.get("ts", ""))
        phase   = rec.get("phase", "")
        content = clean(rec.get("content", ""))

        label = ROLE_LABEL.get(role, role.upper())
        ph    = f"  ({phase})" if phase else ""
        lines.append(f"[{label}]  {ts}{ph}")
        lines.append("-" * 72)
        for cl in content.split("\n"):
            lines.append("  " + cl)
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved plain text → {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
def load_records(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main():
    parser = argparse.ArgumentParser(
        description="Pretty-print chat_history.jsonl  (HTML, plain text, or terminal)",
        epilog="When no arguments are given, INPUT_FILE / OUTPUT_FILE at the top of the script are used."
    )
    parser.add_argument("jsonl", nargs="?", help="Input .jsonl file (overrides INPUT_FILE)")
    parser.add_argument("--out", metavar="FILE", help="Output file: .html or .txt (overrides OUTPUT_FILE)")
    parser.add_argument("--no-color", action="store_true", help="Terminal output without ANSI colours")
    args = parser.parse_args()

    input_path  = args.jsonl if args.jsonl else INPUT_FILE
    output_path = args.out   if args.out   else OUTPUT_FILE

    records = load_records(input_path)

    if output_path is None:
        render_terminal(records, no_color=args.no_color)
    elif output_path.lower().endswith(".html"):
        render_html(records, input_path, output_path)
    else:
        render_txt(records, input_path, output_path)


if __name__ == "__main__":
    main()
