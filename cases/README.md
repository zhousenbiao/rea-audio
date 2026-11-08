# Case files / 案例库

Every directory is one dissected track: `report.html` (human report) + `findings.json`
(machine evidence) + `replication.md` (rebuild recipe). Audio files are deliberately
not redistributed — only the case files.

| case | one-line verdict |
|---|---|
| [`real-world-v1/`](real-world-v1/) | 7 real tracks with verifiable provenance — Suno v5.5 **4/4 detected**, human controls **3/3 acquitted** ([results](real-world-v1/RESULTS.md)) |
| [`demo/`](demo/) | synthetic human-like render — correctly acquitted (HUMAN-MADE) |

## Submit a dissection / 求拆解

Open an issue titled `[dissect] <track>` with:

1. an audio file (or a precise synthesis recipe if you can't share the file),
2. what you want to know (AI verdict? chords? how to rebuild the low end?).

Maintainers run the case, archive the report here, and credit you. Cases that make the
tool say INCONCLUSIVE are especially welcome — they map the honest frontier.
