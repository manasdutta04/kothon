# Product Requirements Document

## Product Name
**Kothon** (কথন) — AI-Native Bengali Subtitle & Closed-Caption Pipeline

## Hackathon Problem Statement
Bengali Subtitle & Closed-Caption Pipeline — Track: Speech & Language

## One-line summary
Kothon takes raw audio/video and produces subtitle/caption output that is not just transcribed but *engineered* — correct Bengali transcription (including code-mixed speech), properly ruled line-by-line formatting, self-validated against subtitle-quality rules, tagged for accessibility, and flagged for sensitive content — so the output is close to what a professional caption reviewer would approve, not a raw ASR dump.

---

## 0. Build Philosophy for This Phase

This phase is about the **system being correct and powerful**, not about how it looks. Concretely:

- **No UI design decisions now.** Build the pipeline so it can be called and produce correct, complete output (as files/JSON) even before any interface exists. Any interface built now is a thin, functional harness only — enough to trigger a run and see the result — not a designed product surface. UI polish is explicitly deferred to a later phase.
- **No authentication unless the system cannot function without it.** This is a solo-operated pipeline for now. Do not build login, accounts, or user management. If a chosen tool/library *requires* minimal auth to function (e.g. an API key), that is configuration, not a feature to build.
- **No persistence layer unless the pipeline needs to remember something across runs.** A single run (upload → process → output) does not need a database. If we need to store multiple past runs for comparison later, that's a deliberate, scoped addition — not a default.
- **Free/open tooling only.** Every model, API, and service used must be free-tier or open-source. No paid keys, no paid infrastructure. Where a paid option is clearly the best in class, note it as a documented future upgrade, not a dependency.
- **Accuracy and robustness are the actual deliverable right now.** The system's worth is judged on whether the output is *right* — correct transcription, correct formatting rules, correctly caught and corrected errors — not on how the run is triggered or displayed.

---

## 1. Problem Statement

Automated subtitle generation for Bengali content is harder than it looks, and most naive pipelines fail in predictable ways:

- **Code-mixing**: real Bengali dialogue routinely mixes in English and Hindi words/phrases mid-sentence. Generic ASR either mistranscribes these or transcribes them phonetically as if they were Bengali.
- **Dialect and colloquial speech**: standard-Bengali-trained models degrade on colloquial, regional, or fast/casual speech — which is most real dialogue.
- **Subtitle formatting is not the same problem as transcription.** A perfectly accurate transcript can still make a *bad subtitle*: lines that are too long, on screen too briefly to read (reading speed / characters-per-second), broken at awkward points instead of natural phrase boundaries, or overlapping in time.
- **No self-checking.** Most pipelines generate once and stop. There is no verification step confirming the output actually satisfies subtitle-quality constraints before it's handed off.
- **No accessibility layer.** Non-speech sound (laughter, phone ringing, music cues) and speaker identity are typically dropped, reducing usefulness for deaf/hard-of-hearing viewers.
- **No compliance layer.** Sensitive or profane content isn't flagged, so review teams have no fast way to locate lines needing editorial attention.

## 2. Goal

Produce a pipeline that turns raw Bengali (or code-mixed Bengali) audio/video into subtitle output that is:

1. **Transcribed accurately**, including code-mixed segments, not just phonetically forced into Bengali script.
2. **Formatted to real subtitle-engineering rules** (reading speed, line length, break points, duration), not a raw one-shot dump of transcript text.
3. **Self-verified** — a dedicated pass checks the formatted output against those rules and corrects violations before final output.
4. **Accessibility-tagged** — non-speech sounds and speaker changes are marked.
5. **Compliance-flagged** — sensitive/profane content is marked per line with a reason.
6. **Fully traceable** — every correction and flag can be traced back to the rule or evidence that produced it.

## 3. Non-Goals (for this phase)

- Not building a designed, polished UI yet — a minimal functional harness is enough to run and inspect output.
- Not building authentication, user accounts, or multi-user support.
- Not building a persistent database of historical runs unless a specific requirement demands it.
- Not doing video-level tasks (segmentation, ad placement, reformatting) — those are other problem statements, out of scope here.
- Not relying on any paid model/API/infrastructure.

## 4. Users (for framing, not for UI design yet)

- A content ops/QC reviewer who needs subtitle output they can trust enough to spot-check rather than re-do line by line.
- A hackathon judge who needs to see, in one run, that the system produces measurably better output than "call an ASR API and save the transcript."

## 5. Core Functional Requirements

### 5.1 Input
- Accept an audio or video file (Bengali or Bengali/English/Hindi code-mixed speech) as the input to a single pipeline run.
- No requirement for batch/multi-file handling in this phase — single-file, single-run correctness comes first.

### 5.2 Transcription
- Produce a timestamped transcript at the segment/utterance level.
- Correctly render code-mixed words in their original language/script where that's the more natural transcription (e.g. keep an English brand name in Latin script rather than transliterating it into Bengali script), rather than forcing everything into Bengali phonetic spelling.
- Record a per-segment confidence signal; low-confidence segments must be visible downstream, never silently treated as correct.

### 5.3 Subtitle Segmentation & Formatting
- Convert the raw timestamped transcript into subtitle-ready lines governed by explicit, configurable rules:
  - maximum characters per line
  - maximum lines per subtitle "card" (typically two)
  - minimum and maximum on-screen duration per card
  - maximum reading speed (characters per second)
  - line breaks placed at natural grammatical/phrase boundaries, not mid-phrase
- These rules must be explicit, inspectable configuration — not implicit behavior buried in a prompt.

### 5.4 Self-Verification
- After formatting, run a dedicated verification pass that checks every subtitle card against the same rule set used to generate it.
- Any violation found must be corrected (or, if uncorrectable without changing meaning, explicitly flagged as an unresolved violation) before the run is considered complete.
- The system must report what was checked, what was found, and what was corrected — this is not an internal-only step, it must be part of the output.

### 5.5 Non-Speech & Speaker Tagging
- Detect and tag non-speech audio events relevant to comprehension (e.g. laughter, phone ringing, notable music cues) as bracketed cues in the caption stream.
- Detect speaker changes where audio signal supports it, and tag speaker turns (even generically, e.g. "Speaker 1 / Speaker 2," if identity isn't resolvable).

### 5.6 Sensitivity/Compliance Flagging
- Scan finalized subtitle lines for profanity or sensitive content categories (violence, slurs, explicit content, etc.).
- Flag each with a category and the specific text that triggered it — never a bare "flagged: true" with no reason.

### 5.7 Output
- Produce standard subtitle file formats (SRT and/or VTT) as the primary deliverable.
- Alongside the subtitle file, produce a structured report (JSON) containing: transcription confidence per segment, formatting-rule check results, corrections made, non-speech/speaker tags, and sensitivity flags — this report is what proves the system's depth in a demo, not just the SRT file itself.

## 6. Non-Functional Requirements

- **Cost**: every model/service used must be free-tier or fully open-source/self-hostable. No paid dependency anywhere in the critical path.
- **Determinism where it matters**: rule-checking (character counts, durations, reading speed) must be computed deterministically in code, never left to an LLM's arithmetic.
- **Traceability**: every automated correction or flag must carry the evidence/reason that produced it.
- **Statelessness by default**: the pipeline should run start-to-finish on one input without requiring a database; if intermediate state is needed, it can live in memory or as temporary files for the duration of a run.
- **No auth**: the pipeline is invoked directly (script, API call, or minimal local harness) without login.

## 7. Success Metrics

- **Transcription accuracy** on Bengali and code-mixed segments specifically (not just overall word error rate — code-mixed segments should be measured separately, since that's the specific failure mode being targeted).
- **Rule-compliance rate**: percentage of final subtitle cards satisfying every formatting rule (should approach 100% after the self-verification pass, by construction).
- **Self-verification catch rate**: number of rule violations caught and corrected in the verification pass versus what the first-pass formatting produced — this number is the clearest evidence of the system doing more than "generate once and hope."
- **Flag precision**: proportion of sensitivity flags that a human would agree are genuinely sensitive (avoid over-flagging noise).

## 8. Key Product Principles

1. **Formatting is engineering, not an afterthought.** Subtitle-quality rules are explicit and checked, not left to model judgment alone.
2. **Verify, don't just generate.** No output is final until it has passed a dedicated check against the same rules used to produce it.
3. **Every automated decision is traceable.** Corrections and flags always carry their evidence and reason.
4. **Free and open by default.** No part of the working pipeline depends on a paid key or paid infrastructure.
5. **System correctness before surface polish.** At this phase, a correct pipeline callable from a script is a complete deliverable; UI is a later, separate concern.

## 9. Open Questions / Deferred Decisions

- Interface: whether the eventual interface is a web app, CLI, or notebook-style runner is not decided yet — deferred until the pipeline itself is proven correct.
- Authentication: deferred entirely; revisit only if a multi-user or public-facing need emerges.
- Persistence: deferred; revisit only if comparing multiple runs over time becomes a real requirement.
- Which specific free ASR model(s) perform best on Bengali code-mixed speech is an empirical question to resolve during build, not a decision to lock in here.
