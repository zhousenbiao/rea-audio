# rea-audio — agent skill

You are working with **rea-audio**, an evidence-first audio reverse-engineering CLI.
Use it to answer questions about audio files, verify claims about tracks, and build
replication loops. Treat it like a forensic instrument, not an oracle.

## Tool contract

Run from the repo root (or after `pip install rea-audio`):

```bash
python -m rea_audio analyze <audio> [-o OUTDIR] [--lang zh|en]   # full case
python -m rea_audio detect <audio>                               # AI verdict only
python -m rea_audio chords <audio>                               # tempo + key + chords
python -m rea_audio replicate <audio>                            # replication plan
```

Outputs of `analyze`: `findings.json` (machine-readable), `report.html` (human),
`replication.md` (rebuild recipe). Analyze is local-only, no network.

## Reading findings.json

Each finding has:
- `status`: `FACT` (measured, reproducible), `HYPOTHESIS` (interpretation),
  `UNKNOWN` (could not decide — respect this, don't paper over it)
- `confidence`: 0..1
- `evidence[]`: the exact measurements (metric, value, unit, detail) behind the verdict
- `caveats[]`: what could invalidate the finding — always read before quoting

## Working rules

1. **Quote verdicts with evidence.** Never say "this track is AI-generated" alone;
   say "E1 cliff at 12.4 kHz (deep rolloff 12.9 kHz), onset jitter 0.004, confidence 71%".
2. **Check transport caveats first.** If the file is <160 kbps MP3 or ≤32 kHz, high-frequency
   evidence is down-weighted by design — say so, and prefer abstaining.
3. **INCONCLUSIVE is an answer.** Report it as-is; do not round it to a side.
4. **Octave ambiguity is real.** The tempo finding may report "60 BPM but 120 nearly as
   strong" — surface both, pick by musical context.
5. **Replication loop:** after generating a clone (e.g. from the Suno prompt in
   replication.md), run `analyze` on the clone and diff `findings.json` fields
   (`meta.bpm`, `meta.rolloff_hz`, `meta.band_shares`, `meta.ai_verdict`) against the
   original. Iterate until they converge.

## Typical task flows

- "Is this Suno?" → `detect`, then read evidence lines E1–E5, then check bitrate caveat.
- "What chords is this?" → `chords`; if key confidence < 0.6, mention runner-up keys.
- "Rebuild this vibe" → `replicate` → use the Suno prompt or studio recipe → verify per rule 5.
- "Compare these two masters" → `analyze` both, diff `meta.band_shares` and `rolloff_hz`.
