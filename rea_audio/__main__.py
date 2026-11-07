# -*- coding: utf-8 -*-
"""rea-audio CLI.

    python -m rea_audio analyze <audio>      # full case: findings + report + replication plan
    python -m rea_audio detect <audio>       # AI-generation vote only
    python -m rea_audio chords <audio>       # tempo + key + chords only
    python -m rea_audio replicate <audio>    # write replication.md for the track
"""
import argparse
import os
import sys
import time

from . import __version__
from .evidence import CaseFile
from .loader import load_audio
from . import analyzers
from .pipeline import analyze_file, write_outputs, replicate as build_replication


def _cmd_analyze(args):
    def progress(msg):
        print("  … {}".format(msg))
    t0 = time.time()
    print("rea-audio {} — opening case: {}".format(__version__, args.audio))
    case = analyze_file(args.audio, progress=progress)
    out = args.out or os.path.splitext(os.path.basename(args.audio))[0] + ".case"
    paths = write_outputs(case, out, lang=args.lang, make_report=not args.no_report)
    print("\n== Case summary ==")
    for line in case.summary_lines():
        print(line)
    print("\nOutputs:")
    for k, p in paths.items():
        print("  {:11s} {}".format(k, p))
    print("Done in {:.1f}s".format(time.time() - t0))


def _mini_case(args, analyzers_to_run):
    case = CaseFile(source=os.path.basename(args.audio))
    case.add(analyzers.format_meta.analyze(args.audio))
    x, sr, ch = load_audio(args.audio, mono=False)
    mono = x.mean(axis=1) if ch > 1 else x[:, 0]
    extra = {}
    if "tempo" in analyzers_to_run:
        f = analyzers.tempo.analyze(mono, sr)
        case.add(f)
        extra["bpm"] = next((float(e.value) for e in f.evidence if e.metric == "autocorrelation peak BPM"), 0.0)
    if "key" in analyzers_to_run:
        case.add(analyzers.key_chords.analyze(mono, sr, bpm=extra.get("bpm", 0.0)))
    if "ai_detect" in analyzers_to_run:
        bitrate = 0.0
        for e in case.findings[0].evidence:
            if e.metric == "mean bitrate":
                bitrate = float(e.value or 0)
        stereo = analyzers.stereo.analyze(x, sr)
        mono_fake = any("numerically identical" in c for c in stereo.caveats)
        transport = {"bitrate_kbps": bitrate, "sr": sr,
                     "stereo": {"mono_fake": mono_fake, "summary": stereo.conclusion}}
        case.add(analyzers.ai_detect.analyze(mono, sr, transport))
    for line in case.summary_lines():
        print(line)
    return case


def _cmd_detect(args):
    _mini_case(args, {"ai_detect"})


def _cmd_chords(args):
    _mini_case(args, {"tempo", "key"})


def _cmd_replicate(args):
    case = analyze_file(args.audio, progress=None)
    md = build_replication(case)
    out = args.out or os.path.splitext(os.path.basename(args.audio))[0] + ".replication.md"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(md)
    print("\nwritten: {}".format(out))


def main(argv=None):
    p = argparse.ArgumentParser(prog="rea-audio",
                                description="Reverse-engineer any audio — evidence-first.")
    p.add_argument("--version", action="version", version="rea-audio " + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="full case file (findings + HTML report + replication plan)")
    a.add_argument("audio")
    a.add_argument("-o", "--out", help="output directory (default: <name>.case/)")
    a.add_argument("--lang", choices=["zh", "en"], default="zh")
    a.add_argument("--no-report", action="store_true")
    a.set_defaults(func=_cmd_analyze)

    d = sub.add_parser("detect", help="AI-generation vote only")
    d.add_argument("audio")
    d.set_defaults(func=_cmd_detect)

    c = sub.add_parser("chords", help="tempo, key & chord progression")
    c.add_argument("audio")
    c.set_defaults(func=_cmd_chords)

    r = sub.add_parser("replicate", help="generate a replication plan (Suno prompt + studio recipe)")
    r.add_argument("audio")
    r.add_argument("-o", "--out")
    r.set_defaults(func=_cmd_replicate)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
