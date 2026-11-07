# -*- coding: utf-8 -*-
"""Evidence system — the REA bloodline of rea-audio.

Every conclusion rea-audio emits must carry verifiable evidence:
numbers, spectra slices, thresholds, and the reasoning step that turned an
observation into a verdict. Findings are triaged into three epistemic classes,
borrowed from REA (Reverse Engineer Anything):

    FACT       — directly measured, reproducible from the file.
    HYPOTHESIS — an interpretation; evidence supports it but alternatives remain.
    UNKNOWN    — we could not decide, and here is why.

This module defines the data model used by every analyzer and by the report.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# Epistemic statuses, ordered by certainty.
FACT = "FACT"
HYPOTHESIS = "HYPOTHESIS"
UNKNOWN = "UNKNOWN"

STATUS_ORDER = {FACT: 0, HYPOTHESIS: 1, UNKNOWN: 2}


@dataclass
class Evidence:
    """A single measurable observation backing a finding.

    `snapshot` holds a small numeric series (e.g. a spectral slice or an
    autocorrelation excerpt) so reports can draw the exact curve the analyzer
    saw when it made the call.
    """

    metric: str                      # e.g. "spectral rolloff frequency"
    value: Any                       # the measured value
    unit: str = ""                   # Hz, dB, ratio, ...
    detail: str = ""                 # how it was measured / what it means
    snapshot: List[float] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)  # optional x labels for snapshot

    def render(self) -> str:
        v = self.value
        if isinstance(v, float):
            v = round(v, 2)
        return "{} = {} {}".format(self.metric, v, self.unit).strip()


@dataclass
class Finding:
    """One conclusion with its evidence chain."""

    id: str                          # short slug, e.g. "tempo"
    title: str                       # human title, e.g. "Tempo & feel"
    status: str                      # FACT / HYPOTHESIS / UNKNOWN
    conclusion: str                  # the verdict, one or two sentences
    confidence: float                # 0..1
    evidence: List[Evidence] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)

    def add(self, ev: Evidence) -> "Finding":
        self.evidence.append(ev)
        return self


class CaseFile:
    """Collects findings for one analyzed track (REA calls this a case)."""

    def __init__(self, source: str):
        self.source = source
        self.findings: List[Finding] = []
        self.meta: Dict[str, Any] = {}

    def add(self, f: Finding) -> Finding:
        self.findings.append(f)
        return f

    def by_status(self, status: str) -> List[Finding]:
        return [f for f in self.findings if f.status == status]

    def summary_lines(self) -> List[str]:
        out = []
        for f in sorted(self.findings, key=lambda x: STATUS_ORDER.get(x.status, 9)):
            mark = {"FACT": "[*]", "HYPOTHESIS": "[?]", "UNKNOWN": "[!]"}.get(f.status, "[ ]")
            out.append("{} {} ({}, conf {:.0%}) — {}".format(
                mark, f.title, f.status.lower(), max(0.0, min(1.0, f.confidence)), f.conclusion))
        return out
