# rea-audio · Reverse-engineer any audio

> Is this track AI-made? What BPM, what key, what chords, how was it mixed — and how do you rebuild it?
> rea-audio breaks audio into **evidence-carrying conclusions** — every number traces back to findings.json, no vibes.

**中文说明：[README.md](README.md)**

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
| E1 | Dual-depth spectral rolloff (cliff vs slope) | −35 dB and −60 dB rolloffs coincide at 8–16.5 kHz (a cliff) | air band reaches 18.5 kHz+, or content slopes into a noise floor | low-bitrate MP3, low-sr sources (auto down-weighted) |
| E2 | Air-band flatness | unnaturally smooth 13–18 kHz floor (σ<1.2 dB) | frequency-axis wiggle like a real noise floor | — |
| E3 | Loudness variance | short-term loudness near-constant | dynamics breathe | over-mastered human tracks |
| E4 | Onset clocking | jitter CV<0.012 (quantized grid) | CV>0.03 (human drift) | quantized recordings |
| E5 | Stereo | numerically identical channels | real stereo image | — |

**Transport down-weighting**: on lossless/high-bitrate files E1/E2 vote at full weight; MP3 <256 kbps drops to 0.6, <160 kbps to 0.25, source sample rate ≤32 kHz to 0.15 — lossy transport imitates the AI cliff, so the tool would rather abstain than accuse.

When evidence splits or total weight is thin, the verdict is `INCONCLUSIVE`. **That is a feature, not a failure.**

## Is it accurate?

The self-test suite is built entirely from **synthetic signals with known ground truth** (fixed seeds, zero downloads, reproducible anywhere):

```bash
python eval/selftest.py
```

Current results ([eval/RESULTS.md](eval/RESULTS.md)): tempo 3/3, key 3/3, ai_detect 2/2.

⚠️ Honest disclaimer: the fixtures are **deliberate archetypes** (clean studio-style render vs band-limited machine-style render). Real tracks sit between them — which is exactly why INCONCLUSIVE exists. Real-world calibration cases are welcome (see [cases/](cases/)).

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

- [ ] demucs stem separation (per-stem verdicts, optional dependency)
- [ ] vocal forensics: autotune traces, pacing, formant placement
- [ ] MCP server (matching the REA ecosystem integration style)
- [ ] known AI-platform fingerprint library (Suno / Udio cliff signatures)
- [ ] real-world calibration set with ROC curves

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
