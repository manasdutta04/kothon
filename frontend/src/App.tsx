import { ChangeEvent, useEffect, useRef, useState } from "react";

type Track = "bn" | "en" | "hi";
type QCIssue = { category: string; score: number; severity: string; evidence: string; recommended_action: string };
type TraceEvent = { stage: string; provider: string; model?: string | null; duration_ms: number; status: string };
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
  events?: TraceEvent[];
};

const API = "http://127.0.0.1:8000/api";
const trackNames: Record<Track, string> = { bn: "বাংলা CC", en: "English", hi: "हिन्दी" };
const stageNames = ["transcription", "segmentation", "verification", "accessibility", "compliance", "translation", "assembly"];

export function App() {
  const [view, setView] = useState<"landing" | "workspace">(
    window.location.pathname === "/app" ? "workspace" : "landing",
  );

  useEffect(() => {
    const handlePopState = () => setView(window.location.pathname === "/app" ? "workspace" : "landing");
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const enterWorkspace = () => {
    window.history.pushState({}, "", "/app");
    setView("workspace");
    window.scrollTo({ top: 0, behavior: "auto" });
  };

  if (view === "landing") return <LandingPage onStart={enterWorkspace} />;
  return <Workspace onBack={() => { window.history.pushState({}, "", "/"); setView("landing"); }} />;
}

function LandingPage({ onStart }: { onStart: () => void }) {
  const pageRef = useRef<HTMLElement>(null);
  const [activeSection, setActiveSection] = useState("landing-hero");

  useEffect(() => {
    const root = pageRef.current;
    if (!root) return;
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) entry.target.classList.add("is-visible");
      });
    }, { threshold: 0.18 });
    const sectionObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) setActiveSection(entry.target.id);
      });
    }, { threshold: 0.35 });
    root.querySelectorAll(".landing-reveal").forEach((element) => revealObserver.observe(element));
    root.querySelectorAll<HTMLElement>("section[id]").forEach((element) => sectionObserver.observe(element));
    return () => { revealObserver.disconnect(); sectionObserver.disconnect(); };
  }, []);

  const navigateTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  const signals = [
    ["01", "Speech signal", "Bengali-first transcription with code-mixed words intact."],
    ["02", "Evidence ledger", "Every risky cue keeps the audio evidence that raised it."],
    ["03", "Review queue", "The highest-risk moments arrive first, ready for a human."],
    ["04", "Timed tracks", "One authoritative timeline, three broadcast-ready outputs."],
  ];
  const principles = [
    ["01", "SIGNAL", "BEFORE CERTAINTY", "Silence and music are evidence, not blank space."],
    ["02", "SYSTEMS", "OVER SCREENS", "A deterministic pipeline keeps decisions inspectable."],
    ["03", "STABLE", "IDENTITIES", "Speaker IDs persist from first appearance to final cue."],
    ["04", "REVIEW", "BY DESIGN", "Uncertainty is surfaced so editors know where to listen."],
  ];
  const navItems = [["landing-hero", "Index"], ["landing-signals", "Signals"], ["landing-work", "Pipeline"], ["landing-principles", "Principles"], ["landing-colophon", "Colophon"]];
  return <main ref={pageRef} className="landing-shell">
    <div className="landing-grid" aria-hidden="true" />
    <aside className="landing-side-nav"><span className="side-word">KOTHON</span><div className="landing-dots">{navItems.map(([id, label]) => <button key={id} className={activeSection === id ? "active" : ""} onClick={() => navigateTo(id)} aria-label={`Go to ${label}`}><i /><span>{label}</span></button>)}</div><span className="side-index">BN / 01</span></aside>
    <nav className="landing-nav"><span className="landing-logo">কথন</span><span className="landing-nav-copy">BENGALI CAPTION INTELLIGENCE</span><span className="landing-status"><i /> OPEN PIPELINE</span></nav>
    <div className="landing-content">
      <section id="landing-hero" className="landing-hero landing-reveal">
        <AnimatedNoiseLanding /><div><span className="landing-kicker">PROBLEM 02 / SPEECH & LANGUAGE</span><SplitFlapWord text="KOTHON" /><h1>THE<br /><em>VOICE</em><br />REMAINS.</h1><p>Broadcast-minded Bengali captions built around evidence, stable speakers, and the moments a machine should never pretend to understand.</p><div className="landing-actions"><button onClick={onStart} className="landing-button">Get started <span>↗</span></button><button onClick={() => navigateTo("landing-signals")} className="landing-text-button">Read the signal ↓</button></div></div>
        <div className="landing-orb" aria-hidden="true"><span>ক</span><span>থ</span><span>ন</span><small>BN / CC</small></div>
      </section>
      <section id="landing-signals" className="landing-section landing-reveal"><div className="landing-section-head"><span>01 / Signals</span><h2>WHAT IT KEEPS</h2></div><div className="signal-strip">{signals.map(([number, title, note]) => <article className="signal-tile" key={number}><div><span>No. {number}</span><span>LIVE SYSTEM</span></div><h3>{title}</h3><b /><p>{note}</p></article>)}</div></section>
      <section id="landing-work" className="landing-section landing-work landing-reveal"><div className="landing-section-head"><span>02 / The pipeline</span><h2>FROM AUDIO<br />TO EVIDENCE</h2></div><div className="work-grid"><article className="work-feature"><span>01 — INGEST</span><strong>Listen before<br />you label.</strong><p>CPU media inspection, speech activity, timestamps and stable speaker turns form the ground truth around every cue.</p></article><article><span>02 — TRANSLATE</span><strong>Three tracks.<br />One timeline.</strong><p>বাংলা CC, English and Hindi inherit the authoritative Bengali timing.</p></article><article><span>03 — QC</span><strong>Review the<br />danger first.</strong><p>Silence hallucinations, uncertain speakers and translation risks are ranked for editors.</p></article><article><span>04 — EXPORT</span><strong>Ready to<br />ship.</strong><p>WebVTT, SRT, QC JSON and a complete trace leave together.</p></article></div></section>
      <section id="landing-principles" className="landing-section landing-principles landing-reveal"><div className="landing-section-head"><span>03 / Principles</span><h2>HOW WE WORK</h2></div><div className="principle-list">{principles.map(([number, lead, tail, note], index) => <article key={number} className={index % 2 ? "align-right" : ""}><span>{number} / {lead}</span><h3><mark>{lead}</mark> {tail}</h3><p>{note}</p><i /></article>)}</div></section>
      <section id="landing-colophon" className="landing-colophon landing-reveal"><span>KOTHON / 2026</span><div><strong>Make uncertainty<br /><em>visible.</em></strong><button onClick={onStart}>Enter the workspace ↗</button></div><span>GROQ READY · CPU SAFE · NO LOCAL MODELS</span></section>
    </div>
  </main>;
}

const FLAP_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

function SplitFlapWord({ text }: { text: string }) {
  const [display, setDisplay] = useState(() => text.split("").map(() => " "));
  const timer = useRef<number | null>(null);
  const animate = () => {
    if (timer.current !== null) window.clearInterval(timer.current);
    let step = 0;
    timer.current = window.setInterval(() => {
      step += 1;
      setDisplay(text.split("").map((char, index) => step > 7 + index * 2 ? char : FLAP_CHARS[Math.floor(Math.random() * FLAP_CHARS.length)]));
      if (step > 7 + text.length * 2 && timer.current !== null) { window.clearInterval(timer.current); timer.current = null; }
    }, 55);
  };
  useEffect(() => { animate(); return () => { if (timer.current !== null) window.clearInterval(timer.current); }; }, []);
  return <div className="split-flap-word" aria-label={text} onMouseEnter={animate}>{display.map((char, index) => <span key={`${index}-${char}`} className={char === text[index] ? "settled" : "flipping"}>{char}</span>)}</div>;
}

function AnimatedNoiseLanding() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    let frame = 0;
    let animationId = 0;
    const resize = () => { canvas.width = Math.max(1, Math.floor(canvas.offsetWidth / 3)); canvas.height = Math.max(1, Math.floor(canvas.offsetHeight / 3)); };
    const draw = () => { frame += 1; if (frame % 2 === 0) { const pixels = context.createImageData(canvas.width, canvas.height); for (let index = 0; index < pixels.data.length; index += 4) { const value = Math.random() * 255; pixels.data[index] = value; pixels.data[index + 1] = value; pixels.data[index + 2] = value; pixels.data[index + 3] = 255; } context.putImageData(pixels, 0, 0); } animationId = window.requestAnimationFrame(draw); };
    resize(); window.addEventListener("resize", resize); draw();
    return () => { window.removeEventListener("resize", resize); window.cancelAnimationFrame(animationId); };
  }, []);
  return <canvas ref={canvasRef} className="landing-noise" aria-hidden="true" />;
}

function Workspace({ onBack }: { onBack: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [report, setReport] = useState<Report | null>(null);
  const [liveEvents, setLiveEvents] = useState<TraceEvent[]>([]);
  const [error, setError] = useState("");

  const chooseFile = (event: ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
    setReport(null);
    setLiveEvents([]);
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
      setLiveEvents([]);
      let status = "queued";
      // Long videos are intentionally asynchronous. A 25-minute source can
      // require many provider requests on the free tier, so do not turn a
      // healthy queued/running job into a false client-side failure.
      const maxPolls = 60 * 60 * 2;
      for (let attempt = 0; attempt < maxPolls; attempt += 1) {
        const statusResponse = await fetch(`${API}/runs/${runId}`);
        if (!statusResponse.ok) throw new Error("The API lost this run while it was processing.");
        const statusPayload = await statusResponse.json();
        status = statusPayload.status;
        setLiveEvents(statusPayload.events ?? []);
        if (status === "completed") break;
        if (status === "failed") throw new Error(statusPayload.error ?? "The pipeline failed.");
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
      if (status !== "completed") throw new Error("This run exceeded the two-hour safety window. The backend may still be processing it; refresh and inspect the run status.");
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
      <nav className="topbar"><button className="back-link" onClick={onBack}>← Kothon</button><span className="mark">কথন</span><span className="eyebrow">caption intelligence / 01</span><span className="status"><i /> {report?.mode === "groq" ? "live groq pipeline" : "fixture mode"}</span></nav>
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
          {!report && <div className="empty-state"><div className="pulse" /><p>{state === "running" ? "Following the signal through each stage… Long media can take several minutes on the free tier." : "Your run will appear here as a reviewable record."}</p>{state === "running" && <ProgressRail events={liveEvents} />}</div>}
          {report && <>
    <div className="stat-grid"><Stat label="cues" value={report.summary.total_cards} /><Stat label="corrected" value={report.summary.cards_corrected} /><Stat label="review queue" value={report.qc_report?.review_queue?.length ?? 0} /><Stat label="flags" value={report.summary.cards_with_sensitivity_flags} /></div>
    <div className="run-note"><span className="run-dot" /> {report.mode === "fixture" ? "Fixture run · structure and QC are live; add GROQ_API_KEY for media transcription" : "Live Groq run · provider output preserved for review"}</div>
    <div className="stage-rail">{(report.events ?? []).map((event) => <div className="stage" key={event.stage}><span className="stage-state">✓</span><span><b>{event.stage}</b><small>{event.provider}{event.model ? ` · ${event.model}` : ""} · {Math.round(event.duration_ms)}ms</small></span></div>)}</div>
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

function ProgressRail({ events }: { events: TraceEvent[] }) {
  const completed = new Map(events.map((event) => [event.stage, event]));
  return <div className="progress-rail">{stageNames.map((stage, index) => { const event = completed.get(stage); const current = !event && (index === 0 || completed.has(stageNames[index - 1])); return <div className={`progress-step ${event ? "complete" : current ? "current" : "pending"}`} key={stage}><span>{event ? "✓" : current ? "·" : "○"}</span><b>{stage}</b></div>; })}</div>;
}

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
