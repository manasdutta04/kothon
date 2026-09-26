import { ChangeEvent, useState } from "react";

type Track = "bn" | "en" | "hi";
type QCIssue = { category: string; score: number; severity: string; evidence: string; recommended_action: string };
type Report = {
  run_id: string;
  mode?: "groq" | "fixture";
  summary: {
    total_cards: number;
    cards_corrected: number;
    cards_with_unresolved_violations: number;
    cards_with_sensitivity_flags: number;
  };
  cards: Array<{
    card: { lines: string[]; start: number; end: number };
    verification?: { verified: boolean; final: { violations: string[] } };
    tagging?: { non_speech_tags: string[]; speaker_label: string | null; low_confidence: boolean };
    compliance?: { flags: Array<{ category: string; triggering_text: string }> };
  }>;
  qc_report?: { review_queue: QCIssue[] };
  tracks?: Record<Track, string[][]>;
};

const API = "http://127.0.0.1:8000/api";
const trackNames: Record<Track, string> = { bn: "বাংলা CC", en: "English", hi: "हिन्दी" };

export function App() {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");

  const chooseFile = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
    setReport(null);
    setError("");
    setState("idle");
  };

  const run = async () => {
    if (!file) return;
    setState("running");
    setError("");
    const body = new FormData();
    body.append("file", file);
    try {
      const created = await fetch(`${API}/runs`, { method: "POST", body });
      if (!created.ok) throw new Error("The API rejected this run.");
      const { run_id: runId } = await created.json();
      const result = await fetch(`${API}/runs/${runId}/result`);
      if (!result.ok) throw new Error("The run did not produce a report.");
      setReport(await result.json());
      setState("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown pipeline error");
      setState("error");
    }
  };

  return (
    <main className="shell">
      <nav className="topbar"><span className="mark">কথন</span><span className="eyebrow">caption intelligence / 01</span><span className="status"><i /> {report?.mode === "groq" ? "live groq pipeline" : "fixture mode"}</span></nav>
      <section className="hero">
        <div className="hero-copy">
          <p className="kicker">Bengali subtitle engineering</p>
          <h1>Make every<br /><em>word</em> count.</h1>
          <p className="lede">Kothon turns Bengali and code-mixed speech into captions with a visible chain of evidence — from transcription to the final rule check.</p>
        </div>
        <div className="orb" aria-hidden="true"><span>ক</span><span>থ</span><span>ন</span></div>
      </section>
      <section className="workspace">
        <div className="upload-card">
          <div className="card-label"><span>01</span><span>Source media</span></div>
          <label className="dropzone">
            <input type="file" accept="audio/*,video/*" onChange={chooseFile} />
            <span className="upload-icon">↑</span>
            <strong>{file ? file.name : "Drop a Bengali recording here"}</strong>
            <small>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to inspect` : "Audio or video · one file per run"}</small>
          </label>
          <button className="run-button" disabled={!file || state === "running"} onClick={run}>{state === "running" ? "Processing…" : "Run caption pipeline"}<span>↗</span></button>
          {error && <p className="error">{error}</p>}
        </div>
        <div className="evidence-card">
          <div className="card-label"><span>02</span><span>Evidence ledger</span></div>
          {!report && <div className="empty-state"><div className="pulse" /><p>{state === "running" ? "Following the signal through each stage…" : "Your run will appear here as a reviewable record."}</p></div>}
          {report && <>
            <div className="stat-grid"><Stat label="cues" value={report.summary.total_cards} /><Stat label="corrected" value={report.summary.cards_corrected} /><Stat label="review queue" value={report.qc_report?.review_queue?.length ?? 0} /><Stat label="flags" value={report.summary.cards_with_sensitivity_flags} /></div>
            <div className="run-note"><span className="run-dot" /> {report.mode === "fixture" ? "Fixture run · structure and QC are live; add GROQ_API_KEY for media transcription" : "Live Groq run · provider output preserved for review"}</div>
            <div className="card-list">{report.cards.map((item, index) => <CueCard key={index} item={item} index={index} tracks={report.tracks} />)}</div>
            <QCQueue issues={report.qc_report?.review_queue ?? []} />
            <div className="downloads"><a href={`${API}/runs/${report.run_id}/files/bengali-vtt`}>Bengali VTT ↗</a><a href={`${API}/runs/${report.run_id}/files/english-srt`}>English SRT ↗</a><a href={`${API}/runs/${report.run_id}/files/hindi-srt`}>Hindi SRT ↗</a><a href={`${API}/runs/${report.run_id}/files/qc-json`}>QC JSON ↗</a></div>
          </>}
        </div>
      </section>
      <footer><span>Designed for Bengali-first review</span><span>Deterministic where it matters · transparent where it doesn’t</span></footer>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number }) { return <div><strong>{value}</strong><span>{label}</span></div>; }

function CueCard({ item, index, tracks }: { item: Report["cards"][number]; index: number; tracks?: Record<Track, string[][]> }) {
  return <article className="subtitle-card">
    <div className="cue-heading"><div className="time">Cue {String(index + 1).padStart(2, "0")} · {item.card.start.toFixed(2)} — {item.card.end.toFixed(2)}s</div><span className="cue-id">#{String(index + 1).padStart(2, "0")}</span></div>
    <div className="track-grid">{(["bn", "en", "hi"] as Track[]).map((language) => <TrackPanel key={language} language={language} lines={tracks?.[language]?.[index] ?? (language === "bn" ? item.card.lines : ["Translation unavailable"])} />)}</div>
    <div className="chips"><span className={item.verification?.verified ? "chip good" : "chip warn"}>{item.verification?.verified ? "verified" : "review"}</span>{item.tagging?.speaker_label && <span className="chip">{item.tagging.speaker_label}</span>}{item.tagging?.low_confidence && <span className="chip warn">low confidence</span>}{item.compliance?.flags.map((flag) => <span className="chip danger" key={flag.triggering_text}>{flag.category}</span>)}</div>
  </article>;
}

function TrackPanel({ language, lines }: { language: Track; lines: string[] }) {
  return <div className={`track-panel track-${language}`}><span className="track-label">{trackNames[language]}</span><p>{lines.map((line, index) => <span key={`${line}-${index}`}>{line}</span>)}</p></div>;
}

function QCQueue({ issues }: { issues: QCIssue[] }) {
  return <section className="qc-queue"><div className="queue-heading"><span>Ranked QC queue</span><small>highest risk first</small></div>{issues.length === 0 ? <p className="queue-empty">No review issues were raised by the current run.</p> : issues.slice(0, 6).map((issue, index) => <div className="issue-row" key={`${issue.category}-${index}`}><strong>{String(index + 1).padStart(2, "0")}</strong><span><b>{issue.category.replaceAll("_", " ")}</b><small>{issue.evidence} {issue.recommended_action}</small></span><em>{Math.round(issue.score)}</em></div>)}</section>;
}
