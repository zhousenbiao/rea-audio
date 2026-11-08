# -*- coding: utf-8 -*-
"""Pipeline orchestration — one pass over the file, one case file out."""
import json
import os
import time
from dataclasses import asdict
from typing import Dict, Optional

from . import analyzers
from .evidence import CaseFile, Finding, STATUS_ORDER
from .loader import load_audio
from .replication import suno


def analyze_file(path: str, progress=None) -> CaseFile:
    def tick(msg):
        if progress:
            progress(msg)

    case = CaseFile(source=os.path.basename(path))

    tick("container facts")
    fmt = analyzers.format_meta.analyze(path)
    case.add(fmt)
    bitrate_kbps = 0.0
    codec = ""
    for e in fmt.evidence:
        if e.metric == "mean bitrate":
            bitrate_kbps = float(e.value or 0)
        elif e.metric == "container":
            codec = str(e.value or "")

    tick("loading audio")
    x_stereo, sr, channels = load_audio(path, mono=False)
    mono = x_stereo.mean(axis=1) if channels > 1 else x_stereo[:, 0]

    tick("tempo")
    tempo_f = analyzers.tempo.analyze(mono, sr)
    case.add(tempo_f)
    bpm = 0.0
    for e in tempo_f.evidence:
        if e.metric == "autocorrelation peak BPM":
            bpm = float(e.value)

    tick("key & chords")
    case.add(analyzers.key_chords.analyze(mono, sr, bpm=bpm))

    tick("stereo field")
    stereo_f = analyzers.stereo.analyze(x_stereo, sr)
    case.add(stereo_f)
    stereo_summary = stereo_f.conclusion
    mono_fake = any("numerically identical" in c for c in stereo_f.caveats)

    tick("spectral balance")
    spec_f, spec_m = analyzers.spectrum.analyze(mono, sr)
    case.add(spec_f)

    tick("structure")
    case.add(analyzers.structure.analyze(mono, sr))

    tick("AI-generation vote")
    transport = {"bitrate_kbps": bitrate_kbps, "sr": sr, "codec": codec,
                 "stereo": {"mono_fake": mono_fake, "summary": stereo_summary}}
    ai_f = analyzers.ai_detect.analyze(mono, sr, transport)
    case.add(ai_f)

    case.meta = {
        "sr": sr, "channels": channels, "bpm": bpm,
        "rolloff_hz": spec_m["rolloff_hz"],
        "band_shares": spec_m["band_shares"],
        "ai_verdict": getattr(ai_f, "meta_verdict", "N/A"),
    }
    return case


def case_to_dict(case: CaseFile) -> dict:
    return {
        "source": case.source,
        "meta": case.meta,
        "findings": [asdict(f) for f in
                     sorted(case.findings, key=lambda x: STATUS_ORDER.get(x.status, 9))],
    }


def replicate(case: CaseFile) -> str:
    """Build the human-readable replication plan (markdown) from the case file."""
    return suno.build_plan(case)


def write_outputs(case: CaseFile, out_dir: str, lang: str = "zh", make_report: bool = True) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    jpath = os.path.join(out_dir, "findings.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(case_to_dict(case), fh, ensure_ascii=False, indent=2)
    paths["json"] = jpath

    rpath = os.path.join(out_dir, "replication.md")
    with open(rpath, "w", encoding="utf-8") as fh:
        fh.write(replicate(case))
    paths["replication"] = rpath

    if make_report:
        from .report import render_html
        hpath = os.path.join(out_dir, "report.html")
        with open(hpath, "w", encoding="utf-8") as fh:
            fh.write(render_html(case, lang=lang))
        paths["report"] = hpath
    return paths
