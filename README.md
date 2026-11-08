# rea-audio · Reverse-engineer any audio

**English** | [简体中文](README_CN.md)

![hero](docs/hero.gif)

> Is this track AI-made? What BPM, what key, what chords, how was it mixed — and how do you rebuild it?
> rea-audio breaks audio into **evidence-carrying conclusions** — every number traces back to findings.json, no vibes.

`rea-audio` is a CLI audio forensics tool: hand it any audio file (wav / flac / ogg / mp3) and it produces a **case file**:

- 🥁 **Tempo** — BPM, with octave-ambiguity flagged instead of hidden
- 🎹 **Harmony** — key (major/minor) + bar-by-bar chord progression
- 🎚️ **Spectrum & stereo** — 8-band energy, dual-depth rolloff, inter-channel correlation and width
- 🧩 **Structure** — section segmentation with energy labels (honestly filed as *hypothesis*)
- 🤖 **AI verdict** — five independent evidence lines vote AI-GENERATED / HUMAN-MADE / INCONCLUSIVE, **each vote shows its numbers, thresholds, and what weakened it**
- 🎯 **Replication plan** — style fingerprint → Suno-style prompt, studio recipe, and a verify-your-clone step

The methodology is inherited from [REA (Reverse Engineer Anything)](https://github.com/morluto/rea): **conclusions must carry evidence, and facts / hypotheses / unknowns stay separated.** rea-audio is an independent community derivative with no affiliation to the REA project (see [Credits](#credits)).

## Quick start

```bash
pip install numpy soundfile        # the only deps (numpy/soundfile/jinja2)
python -m rea_audio analyze your_track.mp3
```

Writes `<your_track>.case/`:

| file | what it is |
|---|---|
| `report.html` | human-readable case report (self-contained, screenshot-ready) |
| `findings.json` | all findings + evidence, machine-readable |
| `replication.md` | the rebuild recipe: style fingerprint + Suno prompt + studio chain |

Subcommands:

```bash
python -m rea_audio detect your_track.mp3     # AI verdict only
python -m rea_audio chords your_track.mp3     # tempo/key/chords only
python -m rea_audio replicate your_track.mp3  # replication plan only
```

## How the AI verdict works (and when it refuses to guess)

Not a black-box classifier — a vote over five **auditable evidence lines**:

| # | Evidence | Votes AI | Votes human | Can be faked by |
|---|---|---|---|---|
| E1 | Generation-band edge (16–19 kHz vs 13–15 kHz decay, calibrated on real tracks) | air band drops ≥15 dB (Suno v5 measured −19…−33 dB) | air band flat (human recordings measured −0.2…−4.5 dB) with persistent energy | low-bitrate MP3, low-sr sources (down-weighted by measured bandwidth) |
| E2 | Air-band texture | — | analog-floor wiggle, once the air band demonstrably exists | — |
| E3 | Loudness variance | short-term loudness near-constant | dynamics breathe | over-mastered human tracks |
| E4 | Onset clocking | jitter CV<0.012 (quantized grid) | — | quantized recordings |
| E5 | Stereo | numerically identical channels | real stereo image | — |

**Transport down-weighting**: E1's trust is judged by the *measured* bandwidth — deep rolloff ≥17 kHz (the air band demonstrably survived transport) or lossless FLAC/WAV votes at full weight; MP3 scales 0.25–0.75 by bitrate; at source sample rates ≤32 kHz, E1 abstains. Lossy transport imitates the AI band fingerprint, so the tool would rather abstain than accuse.

When evidence splits or total weight is thin, the verdict is `INCONCLUSIVE`. **That is a feature, not a failure.**

## Is it accurate?

**Real-track calibration** ([cases/real-world-v1/](cases/real-world-v1/RESULTS.md), verifiable provenance, audio deliberately not redistributed):

| Group | Result | Dominant evidence (air-band edge) |
|---|---|---|
| Suno v5.5 ×4 (HF dataset `Kukedlc/suno-ai-music-dataset`, CC-BY-4.0, API metadata verified) | **4/4 detected AI** | −18.7…−32.9 dB (steep edge) |
| Human-made ×3 (Wikimedia Commons PD/CC0 + Kevin MacLeod CC-BY-4.0) | **3/3 human, zero false positives** | −0.2…−4.5 dB (flat air band) |

**Synthetic self-test** (mathematically generated ground truth, fixed seeds, zero downloads):

```bash
python eval/selftest.py
```

Current results ([eval/RESULTS.md](eval/RESULTS.md)): tempo 3/3, key 3/3, ai_detect 2/2.

⚠️ Honest disclaimer: the human controls lean classical/acoustic while the AI set is pop/electronic — style and provenance are not fully decorrelated yet. Modern mastered-pop controls are especially welcome via issues. When evidence splits, the verdict is INCONCLUSIVE — a feature, not a failure.

## For agents (Claude Code / Codex / Cursor)

Feed [prompts/rea-audio-skill.md](prompts/rea-audio-skill.md) to your coding agent and it can run the full listen → dissect → verdict → rebuild → verify loop autonomously.

## How it works (30-second version)

```
audio ─→ container facts ─→ tempo (spectral-flux autocorrelation) ─→ key/chords (Krumhansl-Schmuckler)
      └→ spectrum (LTAS / dual rolloff) ─→ stereo (mid/side) ─→ structure (novelty)
                     ↓
     five-evidence vote (AI verdict) ──→ case file: facts/hypotheses/unknowns + evidence tables
                     ↓
        replication plan (Suno prompt + studio recipe)
```

Pure numpy + soundfile + jinja2. No GPU, no model downloads, no network calls. A 4-minute track analyzes in ~10 seconds.

## Roadmap

- [x] Real-world calibration set (Suno v5.5 4/4, human controls 3/3 — [cases/real-world-v1/](cases/real-world-v1/))
- [ ] Widen controls: modern mastered pop (decorrelate style from provenance)
- [ ] demucs stem separation (per-stem verdicts, optional dependency)
- [ ] Vocal forensics: autotune traces, pacing, formant placement
- [ ] MCP server (matching the REA ecosystem integration style)
- [ ] Other AI-platform fingerprints (Udio / Stable Audio edge signatures)
- [ ] ROC curves and threshold sensitivity analysis

## Community: request a dissection

Open an issue with an audio file (or a synthesis description) plus your question; maintainers run a full case and archive the report under [cases/](cases/). Every case is content.

## Credits

- **[REA (Reverse Engineer Anything)](https://github.com/morluto/rea)** — the methodology donor: "conclusions carry evidence", "facts / hypotheses / unknowns stay separated". rea-audio is an independent community project, **not affiliated with or endorsed by REA**.
- **[rea-video](https://github.com/JuneYaooo/rea-video)** — proved the "port REA methodology to a mainstream medium" route; rea-audio applies it to audio.

## Disclaimer

- The AI verdict is a **heuristic evidence chain, not forensic proof**. Quote it together with its evidence and confidence.
- For study and research. Replication plans explain how production works — they are not permission to copy someone's record.
- Don't use it to accuse a musician. `INCONCLUSIVE` means "keep investigating, quietly."

## License

MIT
