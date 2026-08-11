# Movie Commentary Workflow

[中文](README.md) | [English](README.en.md)

An auditable movie-commentary production workflow for Codex. A single lead-director agent maintains creative continuity across full-film understanding, first-person writing, character voice production, shot selection, rendering, and final review, while evidence, state locks, and user approval gates keep every adopted decision traceable.

## Project scope

The current `v0.1` is the **Skills Edition**. It provides:

- eight composable Codex skills;
- a production state machine from shot indexing through final verification;
- data contracts for projects, edit plans, audio mixes, and second reviews;
- voice tooling for Qwen, MiniMax, Fish Audio, and Volcengine ASR;
- project templates, JSON Schemas, privacy scanning, and state validation.

This is not a one-click generator. Indexing, directing, and rendering still require the lead agent to inspect continuous source footage with sound and make creative decisions. Generic indexing and rendering executors remain future work.

## Core principles

1. **One lead-director agent:** Skills are stage-specific capabilities, not separate permanent roles that hand off and lose context.
2. **Source evidence comes first:** Subtitles, vision models, and technical cuts help retrieve material but never replace continuous source footage with sound.
3. **Show users a real sample early:** Each sample gets at most one focused internal revision before user review.
4. **Strict on critical facts, flexible on ordinary narration:** Identity, actions, props, and reversals must be accurate; emotion and transitions are judged by overall comprehension and viewing experience.
5. **A file is not an adopted version:** Only locks recorded in `production/state.json` establish the official version.
6. **Creative and technical responsibilities stay separate:** Directing decides shots and sound intent; rendering faithfully executes the locked plan.

## Workflow

```text
INDEX_VERIFIED
→ DRAFT_READY
→ DIRECTOR_SCRIPT_REVIEW
→ SCRIPT_LOCKED
→ VOICE_LOCKED
→ NARRATION_LOCKED
→ DIRECTOR_PROXY_PLAN_LOCKED
→ DIRECTOR_PROXY_RENDERED
→ USER_CREATIVE_REVIEW
↔ revise from user feedback
→ USER_SAMPLE_APPROVED
→ DIRECTOR_PLAN_LOCKED
→ FINAL_RENDERED
→ SECOND_REVIEW
→ SECOND_REVIEW_PASS
→ FINAL_VERIFIED
```

The detailed [workflow](docs/workflow.md) and [architecture guide](docs/architecture.md) are currently maintained in Chinese.

## Quick start

Requirements:

- Codex;
- Python 3.11 or later;
- `ffmpeg` and `ffprobe`;
- optional: `uv` for isolated Python dependencies;
- optional: supported voice-provider accounts and voice material you have the right to use.

Install validation dependencies:

```bash
python -m pip install -e '.[dev]'
```

Check that the public repository contains no private artifacts:

```bash
python scripts/check_repository.py
```

Validate the metadata-only example:

```bash
python scripts/validate_project.py examples/synthetic-demo
```

Before connecting an older private project to the stricter state contract, read the Chinese [state migration guide](docs/migration.md) and do not overwrite the existing state file.

To begin a real film project, copy `templates/film-project/` into a **private directory outside this repository**, fill in the local source information, and then use Codex:

```text
Use $movie-master-director to take over this film project and continue from its current locked state.
```

## Skills

| Skill | Responsibility |
|---|---|
| `movie-master-director` | Single entry point, state recovery, and stage coordination |
| `movie-index` | Shot, subtitle, keyframe, and visual-evidence indexing |
| `movie-first-person-writer` | Full-film understanding and first-person narration writing |
| `movie-voice-tts` | Voice auditions, full narration, and timestamps |
| `movie-direct` | Script preflight, narrative beats, picture, and sound planning |
| `movie-render-qa` | Faithful rendering and technical validation |
| `movie-second-review` | Two-pass independent review of the final render |
| `movie-batch-director` | Isolated alternatives only when the user explicitly requests parallel candidates |

Only `movie-master-director` is the user-facing entry point. The remaining skills are capabilities it loads at the appropriate production stage, not additional project owners.

## Privacy and rights boundary

This repository contains no movie source files, subtitles, stills, evidence frames, rendered videos, voice references, cloned voices, model weights, API keys, or real project state. Real projects stay outside the repository by default, and you should only process material you have the right to use.

Before committing changes, run:

```bash
python scripts/check_repository.py
python -m pytest
```

See the Chinese [public/private boundary guide](docs/open-source-boundary.md) for the full isolation policy.

## License

The code, skills, and project documentation are licensed under the [Apache License 2.0](LICENSE). Third-party services, models, movie material, and voices remain subject to their own terms and rights.
