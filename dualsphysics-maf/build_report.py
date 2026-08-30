#!/usr/bin/env python3
"""Generate self-contained HTML reports from DualSPHysics agent run directories.

Each run directory (``runs/run_<ts>/``) already contains everything we need:
  - ``chat_history.jsonl``  — the user ↔ agent conversation (with input-image refs)
  - ``Case_Def.xml``        — the agent-generated case XML
  - ``out/*.png``           — rendered geometry image(s)
  - ``out/*.vtk``           — ParaView files

This tool renders, per case, a single self-contained ``index.html`` (images
base64-embedded, CSS inlined) plus copies the ``.vtk`` files alongside for
download, and writes a top-level ``index.html`` linking all cases.

Usage:
    # explicit run dirs, with nice case titles
    python build_report.py --out report \
        "Case 1: 2D dam-break=runs/run_20260420_004748" \
        "Case 2: 3D barrier=runs/run_20260420_011025"

    # or just point at run dirs (title = dir name)
    python build_report.py --out report runs/run_20260420_004748 runs/run_...

    # or auto-pick the N most recent runs
    python build_report.py --out report --latest 5
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent

_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif"}
_INPUT_IMG_RE = re.compile(r"^\[input-image\]\s+(.+)$")
_INPUT_MESH_RE = re.compile(r"^\[input-mesh\]\s+(.+)$")


# ── helpers ──────────────────────────────────────────────────────────────────
def data_uri(path: Path) -> str | None:
    """Return a base64 data: URI for an image file, or None if unreadable."""
    try:
        mime = _MIME.get(path.suffix.lower(), "application/octet-stream")
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def resolve_input_path(ref: str, base: Path) -> Path | None:
    """Resolve an input-image reference (e.g. 'datalake/6_test_1.png') to a file."""
    for cand in (base / ref, base / "datalake" / Path(ref).name, Path(ref)):
        if cand.is_file():
            return cand
    return None


def read_history(run_dir: Path) -> list[dict]:
    path = run_dir / "chat_history.jsonl"
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def render_content(text: str) -> str:
    """Render message text: escape HTML, turn ``` fences into <pre> code blocks,
    preserve whitespace/ascii-art elsewhere via white-space: pre-wrap."""
    parts = re.split(r"```[a-zA-Z0-9_]*\n?", text)
    # Odd indices are inside code fences
    out = []
    for i, seg in enumerate(parts):
        if i % 2 == 1:
            out.append(f'<pre class="code">{html.escape(seg.rstrip())}</pre>')
        elif seg.strip():
            out.append(f'<div class="text">{html.escape(seg)}</div>')
    return "\n".join(out) or f'<div class="text">{html.escape(text)}</div>'


# ── per-case rendering ───────────────────────────────────────────────────────
def find_case_xml(run_dir: Path) -> Path | None:
    for cand in (run_dir / "Case_Def.xml", run_dir / "out" / "Case_Def.xml"):
        if cand.is_file():
            return cand
    xmls = sorted((run_dir / "out").glob("*.xml")) if (run_dir / "out").is_dir() else []
    return xmls[0] if xmls else None


def output_pngs(run_dir: Path) -> list[Path]:
    out = run_dir / "out"
    return sorted(out.glob("*.png")) if out.is_dir() else []


def vtk_files(run_dir: Path) -> list[Path]:
    out = run_dir / "out"
    return sorted(out.glob("*.vtk")) if out.is_dir() else []


def first_user_prompt(records: list[dict]) -> str:
    for r in records:
        if r.get("role") == "user":
            c = r.get("content", "")
            if not (_INPUT_IMG_RE.match(c) or _INPUT_MESH_RE.match(c)):
                return c
    return ""


PHASE_LABEL = {
    "planning": "Planning",
    "setup_review": "Setup Review (human-in-the-loop)",
    "results_loop": "Results Analysis (human-in-the-loop)",
}


def render_case(title: str, run_dir: Path, base: Path, case_out: Path) -> dict:
    """Render one case's HTML into case_out/index.html; return summary dict for the index."""
    case_out.mkdir(parents=True, exist_ok=True)
    records = read_history(run_dir)

    # conversation blocks
    convo: list[str] = []
    last_phase = None
    for r in records:
        role = r.get("role", "")
        phase = r.get("phase", "")
        content = r.get("content", "")
        ts = r.get("ts", "")

        if phase != last_phase:
            convo.append(f'<div class="phase-divider">{html.escape(PHASE_LABEL.get(phase, phase or "—"))}</div>')
            last_phase = phase

        m_img = _INPUT_IMG_RE.match(content)
        m_mesh = _INPUT_MESH_RE.match(content)
        if m_img:
            p = resolve_input_path(m_img.group(1).strip(), base)
            uri = data_uri(p) if p else None
            if uri:
                convo.append(
                    f'<div class="msg attach"><div class="badge">input image</div>'
                    f'<div class="attach-name">{html.escape(m_img.group(1).strip())}</div>'
                    f'<img class="shot" src="{uri}" alt="input image"></div>'
                )
            else:
                convo.append(f'<div class="msg attach"><div class="badge">input image (missing)</div>'
                             f'<div class="attach-name">{html.escape(m_img.group(1).strip())}</div></div>')
            continue
        if m_mesh:
            convo.append(f'<div class="msg attach"><div class="badge">input mesh</div>'
                         f'<div class="attach-name">{html.escape(Path(m_mesh.group(1)).name)}</div></div>')
            continue

        short_ts = ts.split("T")[-1][:8] if "T" in ts else ""
        convo.append(
            f'<div class="msg {html.escape(role)}">'
            f'<div class="msg-head"><span class="who">{html.escape(role)}</span>'
            f'<span class="ts">{html.escape(short_ts)}</span></div>'
            f'{render_content(content)}</div>'
        )

    # outputs
    out_imgs = []
    for png in output_pngs(run_dir):
        uri = data_uri(png)
        if uri:
            out_imgs.append(f'<figure><img class="shot" src="{uri}" alt="{html.escape(png.name)}">'
                            f'<figcaption>{html.escape(png.name)}</figcaption></figure>')
    outputs_html = "\n".join(out_imgs) or '<p class="muted">No rendered geometry image found.</p>'

    # generated xml
    xml_path = find_case_xml(run_dir)
    if xml_path:
        xml_txt = html.escape(xml_path.read_text(encoding="utf-8", errors="replace"))
        xml_html = (f'<details><summary>Show generated <code>{html.escape(xml_path.name)}</code> '
                    f'({len(xml_txt.splitlines())} lines)</summary>'
                    f'<pre class="code xml">{xml_txt}</pre></details>')
    else:
        xml_html = '<p class="muted">No case XML found.</p>'

    # vtk files: copy alongside
    vtks = vtk_files(run_dir)
    vtk_links = []
    if vtks:
        vdir = case_out / "vtk"
        vdir.mkdir(exist_ok=True)
        for v in vtks:
            shutil.copy2(v, vdir / v.name)
            vtk_links.append(f'<li><a href="vtk/{html.escape(v.name)}" download>{html.escape(v.name)}</a></li>')
    vtk_html = (f'<p>Open these in ParaView to inspect the particle configuration:</p>'
                f'<ul class="files">{"".join(vtk_links)}</ul>') if vtk_links else \
               '<p class="muted">No ParaView (.vtk) files found.</p>'

    thumb = data_uri(output_pngs(run_dir)[0]) if output_pngs(run_dir) else None
    prompt = first_user_prompt(records)

    page = CASE_TEMPLATE.format(
        title=html.escape(title),
        run_dir=html.escape(str(run_dir)),
        css=CSS,
        convo="\n".join(convo) or '<p class="muted">No conversation recorded.</p>',
        outputs=outputs_html,
        xml=xml_html,
        vtk=vtk_html,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    (case_out / "index.html").write_text(page, encoding="utf-8")
    return {"title": title, "dir": case_out.name, "thumb": thumb, "prompt": prompt,
            "n_msg": len([r for r in records if not _INPUT_IMG_RE.match(r.get("content", ""))]),
            "n_vtk": len(vtks)}


def render_index(cases: list[dict], out: Path) -> None:
    cards = []
    for c in cases:
        thumb = f'<img src="{c["thumb"]}" alt="">' if c["thumb"] else '<div class="noimg">no image</div>'
        prompt = html.escape((c["prompt"][:180] + "…") if len(c["prompt"]) > 180 else c["prompt"])
        cards.append(
            f'<a class="card" href="{c["dir"]}/index.html">'
            f'<div class="thumb">{thumb}</div>'
            f'<div class="card-body"><h3>{html.escape(c["title"])}</h3>'
            f'<p class="prompt">{prompt}</p>'
            f'<div class="meta">{c["n_msg"]} messages · {c["n_vtk"]} ParaView files</div></div></a>'
        )
    page = INDEX_TEMPLATE.format(
        css=CSS, cards="\n".join(cards),
        n=len(cases), generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    (out / "index.html").write_text(page, encoding="utf-8")


# ── templates / css ──────────────────────────────────────────────────────────
CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1a1d21;--muted:#6b7280;--line:#e5e7eb;
--user:#eef2ff;--user-bd:#c7d2fe;--assistant:#f0fdf4;--assistant-bd:#bbf7d0;--accent:#4f46e5;}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--card:#161a20;--ink:#e6e8eb;--muted:#9aa4b2;
--line:#262b33;--user:#1e213a;--user-bd:#2f3566;--assistant:#122019;--assistant-bd:#1e4636;--accent:#818cf8;}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:960px;margin:0 auto;padding:32px 20px 80px;}
header h1{font-size:26px;margin:0 0 4px;}header .sub{color:var(--muted);margin-bottom:24px;}
h2{font-size:19px;margin:34px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--line);}
.muted{color:var(--muted);}a{color:var(--accent);}
.phase-divider{margin:22px 0 10px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;
color:var(--muted);font-weight:600;}
.msg{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:10px 0;background:var(--card);}
.msg.user{background:var(--user);border-color:var(--user-bd);}
.msg.assistant{background:var(--assistant);border-color:var(--assistant-bd);}
.msg-head{display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px;}
.who{font-weight:700;text-transform:capitalize;}.ts{color:var(--muted);}
.text{white-space:pre-wrap;word-wrap:break-word;}
.code{white-space:pre;overflow-x:auto;background:rgba(127,127,127,.10);border:1px solid var(--line);
border-radius:8px;padding:10px 12px;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
.msg.attach{display:flex;flex-direction:column;gap:6px;}
.badge{align-self:flex-start;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
background:var(--accent);color:#fff;border-radius:6px;padding:2px 8px;}
.attach-name{font-size:12px;color:var(--muted);font-family:ui-monospace,monospace;}
.shot{max-width:100%;height:auto;border-radius:8px;border:1px solid var(--line);display:block;}
figure{margin:0 0 16px;}figcaption{font-size:12px;color:var(--muted);margin-top:4px;text-align:center;}
details{margin:8px 0;}summary{cursor:pointer;font-weight:600;}
.files{list-style:none;padding:0;}.files li{padding:4px 0;font-family:ui-monospace,monospace;font-size:13px;}
.back{display:inline-block;margin-bottom:16px;font-size:14px;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px;}
.card{display:block;text-decoration:none;color:inherit;background:var(--card);border:1px solid var(--line);
border-radius:14px;overflow:hidden;transition:transform .12s,box-shadow .12s;}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.12);}
.thumb{aspect-ratio:16/10;background:#0b0d10;display:flex;align-items:center;justify-content:center;overflow:hidden;}
.thumb img{width:100%;height:100%;object-fit:cover;}.noimg{color:var(--muted);font-size:13px;}
.card-body{padding:12px 14px;}.card-body h3{margin:0 0 6px;font-size:16px;}
.card-body .prompt{color:var(--muted);font-size:13px;margin:0 0 8px;}
.card-body .meta{font-size:12px;color:var(--muted);}
"""

CASE_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{css}</style></head><body><div class="wrap">
<a class="back" href="../index.html">← All cases</a>
<header><h1>{title}</h1><div class="sub">Run directory: <code>{run_dir}</code></div></header>
<h2>Conversation with the agent</h2>{convo}
<h2>Agent output — geometry</h2>{outputs}
<h2>Agent-generated case XML</h2>{xml}
<h2>ParaView files</h2>{vtk}
<p class="muted" style="margin-top:40px">Generated {generated}</p>
</div></body></html>"""

INDEX_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DualSPHysics Agent — Preprocess Experiments</title><style>{css}</style></head><body><div class="wrap">
<header><h1>DualSPHysics Agent — Preprocess Experiments</h1>
<div class="sub">{n} cases · generated {generated}</div></header>
<div class="grid">{cards}</div></div></body></html>"""


# ── CLI ──────────────────────────────────────────────────────────────────────
def parse_specs(specs: list[str]) -> list[tuple[str, Path]]:
    out = []
    for s in specs:
        if "=" in s and not Path(s).exists():
            title, _, path = s.partition("=")
            out.append((title.strip(), Path(path.strip())))
        else:
            p = Path(s)
            out.append((p.name, p))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="*", help="run dirs, or 'Title=run_dir'")
    ap.add_argument("--out", default="report", help="output directory (default: report)")
    ap.add_argument("--base", default=str(BASE), help="project base dir (for resolving datalake images)")
    ap.add_argument("--latest", type=int, default=0, help="auto-pick N most recent runs/ dirs")
    args = ap.parse_args()

    base = Path(args.base).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if args.latest:
        runs = sorted((base / "runs").glob("run_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        cases = [(p.name, p) for p in runs[: args.latest]]
    else:
        cases = parse_specs(args.specs)

    if not cases:
        ap.error("no run directories given (pass run dirs, 'Title=run_dir', or --latest N)")

    summaries = []
    for i, (title, run_dir) in enumerate(cases, 1):
        run_dir = run_dir if run_dir.is_absolute() else (base / run_dir)
        if not run_dir.is_dir():
            print(f"  ! skip (not a dir): {run_dir}")
            continue
        case_id = f"case{i}"
        print(f"  • {case_id}: {title}  ({run_dir.name})")
        summaries.append(render_case(title, run_dir, base, out / case_id))

    render_index(summaries, out)
    print(f"\nReport written to: {out}/index.html  ({len(summaries)} cases)")


if __name__ == "__main__":
    main()
