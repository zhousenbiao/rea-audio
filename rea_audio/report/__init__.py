# -*- coding: utf-8 -*-
"""Self-contained HTML report — inline CSS, inline SVG charts, no external assets."""
from typing import List

from ..evidence import CaseFile, Finding, Evidence, FACT, HYPOTHESIS, UNKNOWN

_STATUS_STYLE = {
    FACT: ("fact", "#0a7d33", "事实 / FACT"),
    HYPOTHESIS: ("hyp", "#b8860b", "假设 / HYPOTHESIS"),
    UNKNOWN: ("unk", "#666666", "未知 / UNKNOWN"),
}

I18N = {
    "zh": {
        "title": "rea-audio 逆向报告",
        "verdict": "来源判定",
        "sections": "逐项发现",
        "evidence": "证据",
        "confidence": "置信度",
        "caveats": "但书",
        "snapshot": "观测快照",
        "facts": "事实",
        "hyps": "假设",
        "unks": "未知",
        "no_evidence": "（无证据输出）",
    },
    "en": {
        "title": "rea-audio reverse-engineering report",
        "verdict": "Provenance verdict",
        "sections": "Findings",
        "evidence": "Evidence",
        "confidence": "confidence",
        "caveats": "Caveats",
        "snapshot": "Observed snapshot",
        "facts": "facts",
        "hyps": "hypotheses",
        "unks": "unknowns",
        "no_evidence": "(no evidence emitted)",
    },
}


def _svg_bars(snapshot: List[float], labels: List[str], color: str) -> str:
    if not snapshot:
        return ""
    vals = [float(v) for v in snapshot]
    vmin, vmax = min(vals), max(vals)
    rng = (vmax - vmin) or 1.0
    n = len(vals)
    bar_w = 100.0 / n
    parts = []
    for i, v in enumerate(vals):
        h = 5 + 55.0 * (v - vmin) / rng
        x = i * bar_w
        parts.append('<rect x="{:.2f}" y="{:.2f}" width="{:.2f}" height="{:.2f}" rx="1"/>'.format(
            x + bar_w * 0.15, 60 - h, bar_w * 0.7, h))
    # bars live in a stretched SVG; tick labels are plain HTML below it so they
    # never get distorted/clipped by preserveAspectRatio="none"
    if labels:
        shown = [(i, labels[i]) for i in range(0, min(n, len(labels)), max(1, n // 10))]
        ticks = "".join("<span style='flex:1;text-align:center'>{}</span>".format(str(l)[:6])
                        for i, l in shown)
        label_row = "<div style='display:flex;font-size:10px;color:#7a8794;margin-top:2px'>{}</div>".format(ticks)
    else:
        label_row = ""
    return ('<svg viewBox="0 0 100 60" preserveAspectRatio="none" '
            'style="width:100%;height:60px;display:block" '
            'fill="{c}">{bars}</svg>{labels}').format(c=color, bars="".join(parts), labels=label_row)


def _finding_html(f: Finding, t: dict) -> str:
    cls, color, label = _STATUS_STYLE.get(f.status, _STATUS_STYLE[UNKNOWN])
    conf = max(0.0, min(1.0, f.confidence))
    ev_rows = "".join(
        "<tr><td class='m'>{}</td><td class='v'>{}</td><td class='d'>{}</td></tr>".format(
            e.metric, _fmt(e.value), (e.detail or "").replace("<", "&lt;"))
        for e in f.evidence)
    if not ev_rows:
        ev_rows = "<tr><td colspan='3' class='d'>{}</td></tr>".format(t["no_evidence"])
    snaps = ""
    for e in f.evidence:
        if e.snapshot:
            snaps += "<div class='snap'>{} — {}</div>{}".format(
                t["snapshot"], e.metric, _svg_bars(e.snapshot, e.labels or [], color))
    caveats = "".join("<li>{}</li>".format(c.replace("<", "&lt;")) for c in f.caveats)
    return """
<div class="card {cls}">
  <div class="head">
    <span class="badge" style="background:{color}">{label}</span>
    <span class="ftitle">{title}</span>
    <span class="fconf">{conf:.0%} {confword}</span>
  </div>
  <p class="concl">{concl}</p>
  <table class="ev"><thead><tr><th>{evidence}</th><th></th><th></th></tr></thead>
  <tbody>{rows}</tbody></table>
  {snaps}
  {caveats_html}
</div>""".format(cls=cls, color=color, label=label, title=f.title, conf=conf,
                 confword=t["confidence"], concl=f.conclusion.replace("<", "&lt;"),
                 evidence=t["evidence"], rows=ev_rows, snaps=snaps,
                 caveats_html="<ul class='caveats'>{}</ul>".format(caveats) if caveats else "")


def _fmt(v) -> str:
    if isinstance(v, float):
        return "{:.4g}".format(v)
    if isinstance(v, list):
        return ", ".join(_fmt(x) for x in v[:8]) + ("…" if len(v) > 8 else "")
    if isinstance(v, dict):
        return ", ".join("{}: {}".format(k, _fmt(x)) for k, x in list(v.items())[:8])
    return str(v)


def render_html(case: CaseFile, lang: str = "zh") -> str:
    t = I18N.get(lang, I18N["zh"])
    n = {FACT: len(case.by_status(FACT)), HYPOTHESIS: len(case.by_status(HYPOTHESIS)),
         UNKNOWN: len(case.by_status(UNKNOWN))}
    verdict = case.meta.get("ai_verdict", "N/A")
    v_color = {"AI-GENERATED": "#c0392b", "HUMAN-MADE": "#0a7d33"}.get(verdict, "#666")

    cards = "".join(_finding_html(f, t) for f in
                    sorted(case.findings, key=lambda x: {"FACT": 0, "HYPOTHESIS": 1}.get(x.status, 2)))
    return """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — {src}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
         margin: 0; background: #f6f7f9; color: #1c2733; }}
  .wrap {{ max-width: 880px; margin: 0 auto; padding: 28px 20px 60px; }}
  header h1 {{ font-size: 22px; margin: 0 0 4px; }}
  header .src {{ color: #5b6b7b; font-size: 14px; }}
  .verdict {{ display: inline-block; margin: 14px 0 6px; padding: 8px 14px; border-radius: 8px;
             color: #fff; font-weight: 600; }}
  .counts {{ color: #5b6b7b; font-size: 13px; margin-bottom: 20px; }}
  .card {{ background: #fff; border: 1px solid #e3e8ee; border-left: 4px solid #999;
          border-radius: 10px; padding: 14px 16px; margin: 12px 0; }}
  .card.fact {{ border-left-color: #0a7d33; }}
  .card.hyp  {{ border-left-color: #b8860b; }}
  .card.unk  {{ border-left-color: #666; opacity: .92; }}
  .head {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .badge {{ color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 20px; }}
  .ftitle {{ font-weight: 700; }}
  .fconf {{ margin-left: auto; color: #5b6b7b; font-size: 12px; }}
  .concl {{ margin: 8px 0 10px; line-height: 1.55; }}
  table.ev {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  table.ev th {{ text-align: left; color: #8b98a5; font-weight: 500; padding: 2px 6px 4px 0; }}
  table.ev td {{ padding: 3px 6px 3px 0; border-top: 1px dashed #edf0f3; vertical-align: top; }}
  td.m {{ color: #2b3a4a; white-space: nowrap; }}
  td.v {{ font-family: ui-monospace, Consolas, monospace; }}
  td.d {{ color: #7a8794; }}
  .snap {{ font-size: 12px; color: #7a8794; margin-top: 8px; }}
  .caveats {{ color: #8a6d3b; font-size: 12.5px; margin: 8px 0 0; padding-left: 18px; }}
  footer {{ margin-top: 26px; color: #93a1ad; font-size: 12px; line-height: 1.6; }}
</style>
</head>
<body><div class="wrap">
<header>
  <h1>{title}</h1>
  <div class="src">case: {src}</div>
  <div class="verdict" style="background:{v_color}">{verdict_word}: {verdict}</div>
  <div class="counts">{n_fact} {facts} · {n_hyp} {hyps} · {n_unk} {unks}</div>
</header>
{cards}
<footer>
  Every conclusion above carries its measured evidence — that is the rea-audio contract,
  inherited from <b>REA</b> (Reverse Engineer Anything).<br>
  Heuristics, not certainties. Lossy codecs imitate parts of the AI fingerprint;
  read the caveats before quoting a verdict. MIT licensed.
</footer>
</div></body></html>""".format(
        lang=lang, title=t["title"], src=case.source, v_color=v_color,
        verdict_word=t["verdict"], verdict=verdict,
        n_fact=n[FACT], n_hyp=n[HYPOTHESIS], n_unk=n[UNKNOWN],
        facts=t["facts"], hyps=t["hyps"], unks=t["unks"], cards=cards)
