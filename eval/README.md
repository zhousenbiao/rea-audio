# Evaluation protocol

`selftest.py` grades the analyzers against **synthetic fixtures with known ground truth**:

- fixed random seeds — identical results on every machine, no downloads, no licensing
- tempo fixtures: mathematically exact click trains (90 / 120 / 150 BPM); grading accepts
  half/double tempo among reported candidates because octave ambiguity is real and the tool
  reports it rather than hiding it
- key fixtures: pure chord pads in C major / A minor / G major
- AI-detection fixtures: two deliberate archetypes —
  - *human-like*: full-band noise floor, cymbal air bursts, timing drift (±45 ms), breathing
    dynamics, true stereo
  - *AI-like*: content band-limited by construction, flat floor, machine-perfect clocking,
    constant loudness, duplicated channels

Run:

```bash
python eval/selftest.py          # prints the table, rewrites RESULTS.md, exits nonzero on failure
python eval/selftest.py --keep   # also writes fixtures to eval/fixtures/ so you can listen
```

## Why synthetic-only?

Real-world labeled audio (commercial masters vs known Suno renders) carries copyright
constraints and irreproducible labels. Synthetic archetypes give a **lower bound** on
detector sanity: if the analyzer cannot nail deliberately obvious cases, it has no business
near subtle ones. Real-world calibration (with ROC curves, per-platform fingerprints, and a
labeled community set) is on the roadmap — bring your cases to `cases/`.
