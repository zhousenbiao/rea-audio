# -*- coding: utf-8 -*-
"""Container & codec facts — the cheapest evidence in the case file."""
import os

from ..evidence import Evidence, Finding, FACT
from ..loader import load_info


def analyze(path: str) -> Finding:
    info = load_info(path)
    size = os.path.getsize(path)
    bitrate_kbps = 8.0 * size / 1000.0 / info["duration"] if info["duration"] > 0 else 0.0

    f = Finding(
        id="format",
        title="Container & stream facts",
        status=FACT,
        confidence=1.0,
        conclusion="{} {}, {} Hz, {}ch, {:.1f}s, ~{} kbps".format(
            info["format"], info["subtype"], info["sr"], info["channels"],
            info["duration"], int(bitrate_kbps)),
    )
    f.add(Evidence("container", info["format"]))
    f.add(Evidence("codec/subtype", info["subtype"]))
    f.add(Evidence("sample rate", info["sr"], "Hz"))
    f.add(Evidence("channels", info["channels"]))
    f.add(Evidence("duration", round(info["duration"], 2), "s"))
    f.add(Evidence("mean bitrate", int(bitrate_kbps), "kbps",
                   detail="file size / duration; lossy codecs only — never proof of provenance by itself"))
    if info["sr"] <= 22050:
        f.caveats.append("Sample rate <= 22.05 kHz: everything above {:.1f} kHz is missing "
                         "regardless of whether the source was AI.".format(info["sr"] / 2000.0))
    return f
