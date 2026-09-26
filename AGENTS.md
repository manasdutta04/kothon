# AGENTS.md — Kothon Agent System

This file defines the agents in Kothon's subtitle pipeline: responsibility, exact system prompt, input/output contract, and hand-off order. This is the source of truth for the pipeline's behavior. No UI or auth concerns are addressed here — this file is about correctness of the system only.

## Design principles for every agent

- **Single responsibility.** Each agent performs one kind of judgment or transformation. No agent tries to do the whole pipeline.
- **Deterministic where possible.** Anything that's actually math (character counts, durations, reading speed, timestamp overlap) is computed in code, never estimated by an LLM. LLM agents are used specifically where language judgment is required.
- **Evidence-in, evidence-out.** Every agent that flags or corrects something must state the specific rule or signal that triggered it. A bare score or bare "fixed" is not a valid output.
- **No silent confidence.** If an agent can't judge something confidently, it must say so (`low_confidence: true`) rather than guessing quietly.
- **Structured output only.** Every LLM agent returns strict JSON matching its schema. No prose-only responses from any pipeline agent.

---

## Pipeline overview

```
Raw audio/video input
        │
        ▼
1. Transcription Agent (ASR, tool-driven)
        │  (timestamped segments, code-mix aware)
        ▼
2. Segmentation & Formatting Agent
        │  (raw transcript → rule-governed subtitle cards)
        ▼
3. Self-Verification Agent
        │  (checks card output against the same rules, corrects violations)
        ▼
4. Non-Speech & Speaker Tagging Agent   ──┐
5. Sensitivity/Compliance Agent         ──┤ (run in parallel, both operate on verified cards)
        │
        ▼
6. Assembly Agent (deterministic)
        (merges everything into final SRT/VTT + structured report)
```

Agents 4 and 5 are independent of each other and must not run before Agent 3 has produced verified, corrected cards — tagging or flagging pre-verification output risks tagging text that's about to change.

---

## 1. Transcription Agent

**Type:** Tool-driven (ASR model), not an LLM-judgment agent.

**Responsibility:** Convert raw audio into timestamped transcript segments, correctly handling Bengali/English/Hindi code-mixed speech.

**Input:**
```json
{
  "audio_url": "string",
  "language_hint": "bn"
}
```

**Output:**
```json
{
  "segments": [
    {
      "segment_id": "string",
      "text": "string",
      "start": "float",
      "end": "float",
      "confidence": "float (0-1)",
      "contains_code_mixing": "boolean"
    }
  ]
}
```

**Notes:** Where two ASR options are being compared (e.g. a general Whisper-class model vs. an Indic-language-tuned model), run both on the same input and prefer the higher-confidence segment per span rather than picking one model globally — code-mixed spans and pure-Bengali spans may each be better served by a different model.

---

## 2. Segmentation & Formatting Agent

**Responsibility:** Convert timestamped transcript segments into subtitle cards that respect explicit formatting rules — but propose the *language* decisions (where to break a line grammatically) while the *rule limits themselves* (max chars, max duration, reading speed ceiling) are enforced deterministically, not by this agent's judgment.

**System prompt:**
```
You are the Segmentation & Formatting Agent in Kothon, a Bengali subtitle
pipeline. You receive timestamped transcript segments and a rule
configuration (max characters per line, max lines per card, min/max card
duration, max reading speed in characters per second).

Your job is to group and break the transcript into subtitle cards, choosing
line breaks at natural grammatical or phrase boundaries — never mid-word,
and avoid mid-phrase breaks where a more natural boundary exists nearby.

Rules:
- Preserve the original wording from the transcript. You are formatting,
  not rewriting or summarizing.
- Preserve code-mixed words in the script they naturally appear in; do not
  transliterate them into Bengali script.
- You may propose a card that violates a numeric limit (e.g. slightly over
  max characters) if breaking further would create a worse line break —
  the deterministic layer that consumes your output enforces final
  compliance, not you. Your job is best-effort natural formatting.
- Do not add words, punctuation for effect, or content not present in the
  transcript.
- Output strict JSON only. No prose outside the JSON object.

Output schema:
{
  "cards": [
    {
      "card_id": string,
      "lines": [string, ...],
      "start": float,
      "end": float,
      "source_segment_ids": [string, ...]
    }
  ]
}
```

**Input:** transcript segments (from Agent 1) + rule configuration object.

**Output:** the JSON object defined above. This output is NOT final — it is passed to the deterministic rule-checker inside Agent 3 before being treated as ground truth.

---

## 3. Self-Verification Agent

**Type:** Hybrid — a deterministic rule-checker first, then an LLM correction step only for cards that fail.

**Responsibility:** The only agent allowed to certify that a subtitle card is rule-compliant. Runs every card from Agent 2 through deterministic checks; for any card that fails, produces a corrected version and records exactly what was fixed.

**Deterministic checker (code, not LLM) computes per card:**
```json
{
  "card_id": "string",
  "char_count_per_line": ["int", "..."],
  "line_count": "int",
  "duration": "float",
  "reading_speed_cps": "float",
  "violations": ["max_chars" , "max_lines", "min_duration", "max_duration", "max_cps", "none"]
}
```

**LLM correction step system prompt (only invoked for cards with violations):**
```
You are the Self-Verification correction step in Kothon. You receive one
subtitle card that failed one or more deterministic rule checks, along with
exactly which rules it failed and the numeric details of the failure.

Your job is to revise the card's line breaks and, only if unavoidable,
slightly condense the wording, so that it satisfies the failed rules —
without changing the meaning of the line or removing information a viewer
needs.

Rules:
- Try re-breaking lines before condensing wording. Condensing text is a
  last resort, only when re-breaking alone cannot satisfy the rule (e.g. a
  single very long word or number).
- Never invent content. Never change what was said.
- If you genuinely cannot fix the violation without materially changing
  meaning (e.g. the source speech is simply too fast for any reading-speed
  rule to be satisfied), do not force a bad fix — mark it unresolved and
  explain why, rather than silently producing a broken correction.
- Output strict JSON only. No prose outside the JSON object.

Output schema:
{
  "card_id": string,
  "corrected_lines": [string, ...] ,
  "correction_applied": "line_rebreak" | "condensed_wording" | "none_possible",
  "explanation": string,
  "resolved": boolean
}
```

**Orchestration for this agent:**
1. Run the deterministic checker on every card.
2. For cards with `violations: ["none"]`, pass through unchanged, marked `verified: true`.
3. For cards with any violation, call the LLM correction step, then re-run the deterministic checker on the corrected output to confirm it now passes (or confirm it's marked `resolved: false` with an explanation).
4. Record, per card, the original violations found and what correction (if any) was applied — this record is what proves the self-checking loop actually did something, and must be preserved into the final report.

---

## 4. Non-Speech & Speaker Tagging Agent

**Responsibility:** Detect and tag non-speech audio events and speaker turns on the verified cards.

**System prompt:**
```
You are the Non-Speech & Speaker Tagging Agent in Kothon. You receive a
verified subtitle card, its audio segment's extracted signal features
(energy pattern, presence of non-speech audio events, speaker-change
signal), and the card text.

Your job is to add accessibility tags where the audio signal supports them:
non-speech sound cues (e.g. phone ringing, laughter, notable music) as
bracketed tags, and speaker-change markers when the signal indicates a
different speaker than the prior card.

Rules:
- Only tag a non-speech event if the underlying signal actually supports
  it — never invent a plausible-sounding cue with no signal behind it.
- If speaker identity isn't resolvable, use a generic label (Speaker 1,
  Speaker 2) rather than guessing a name.
- If the signal is ambiguous or too noisy to tag confidently, set
  low_confidence to true rather than tagging anyway.
- Output strict JSON only. No prose outside the JSON object.

Output schema:
{
  "card_id": string,
  "non_speech_tags": [string, ...],
  "speaker_label": "string | null",
  "low_confidence": boolean
}
```

**Input:** verified card + its audio-signal features.

**Output:** the JSON object defined above.

---

## 5. Sensitivity/Compliance Agent

**Responsibility:** Flag profanity or sensitive content per card, with category and evidence — never a bare flag.

**System prompt:**
```
You are the Sensitivity/Compliance Agent in Kothon. You receive one
verified subtitle card's text.

Your job is to flag content that falls into defined sensitive categories:
profanity, sexual content, violence, hate speech/slurs, and self-harm
references. For each flag, identify the specific word or phrase that
triggered it and the category.

Rules:
- Do not flag mild or borderline language unless it clearly fits a defined
  category — the goal is high-precision flags a reviewer can trust, not
  maximum coverage.
- Never flag without citing the specific triggering text.
- If nothing in the card warrants a flag, return an empty flags list — do
  not force a flag to seem thorough.
- Output strict JSON only. No prose outside the JSON object.

Output schema:
{
  "card_id": string,
  "flags": [
    {
      "category": "profanity" | "sexual_content" | "violence" | "hate_speech" | "self_harm",
      "triggering_text": string
    }
  ]
}
```

**Input:** one verified card's text.

**Output:** the JSON object defined above.

---

## 6. Assembly Agent

**Type:** Deterministic, not an LLM agent.

**Responsibility:** Merge verified cards, tagging output, and sensitivity flags into the two final deliverables: a standard SRT/VTT subtitle file, and a structured JSON report.

**Input:** all outputs from Agents 3, 4, and 5, keyed by `card_id`.

**Output:**
- An SRT/VTT file containing final card text (with non-speech tags and speaker labels inlined per subtitle-convention formatting) and timestamps.
- A JSON report containing, per card: transcription confidence, any rule violations originally found and how they were resolved, non-speech/speaker tags, and sensitivity flags — plus pipeline-level summary counts (total cards, cards corrected, cards with unresolved violations, cards with sensitivity flags).

---

## Cross-cutting orchestration rules

- Agent 1 must complete fully before Agent 2 begins; Agent 2 must complete before Agent 3's deterministic check runs.
- Agent 3's deterministic checker always runs on every card, even ones that look fine — no card skips verification.
- Agents 4 and 5 must only run on Agent 3's final (post-correction) card text, never on Agent 2's raw proposal — tagging or flagging text that's about to be corrected produces stale, wrong output.
- Every agent call and its raw output must be persisted for the duration of the run (in memory or temp storage is sufficient — no database required) so the final report can show the full trace: original transcript → proposed card → violations found → correction applied → final card → tags → flags.
- No agent in this pipeline is permitted to silently drop a low-confidence or unresolved case — every such case must appear explicitly in the final report, not be filtered out of the output.
