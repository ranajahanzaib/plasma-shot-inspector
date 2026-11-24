"use client";

import {
  Activity,
  AlertCircle,
  ArrowDownUp,
  ArrowRight,
  Atom,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  Database,
  Download,
  ExternalLink,
  FileSearch,
  Filter,
  Gauge,
  Layers2,
  LoaderCircle,
  Radio,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  SquareActivity,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/v1";
type Shot = Record<string, unknown> & { shot_id: number };
type Audit = {
  id: string;
  shot_id: number;
  status: string;
  report?: {
    shot_id: number;
    findings: Finding[];
    rules_evaluated: number;
    rules_not_evaluated: number;
    limitations: string[];
  };
  error?: string;
};
type Finding = {
  rule_id: string;
  outcome: string;
  severity: string;
  summary: string;
  explanation: string;
  evidence: Record<string, unknown>;
};
type Signal = {
  name: string;
  dimensions: string[];
  shape: number[];
  units?: string;
  source?: string;
};
type Samples = {
  time: number[] | null;
  values: number[];
  units?: string;
  display_only: boolean;
};
type Equilibrium = {
  frame_time: number;
  frame_index: number;
  frame_count: number;
  frame_selection: string;
  r: number[];
  z: number[];
  psi: (number | null)[][];
  psi_units?: string;
  r_units?: string;
  z_units?: string;
  magnetic_axis: number[] | null;
};

function format(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number")
    return new Intl.NumberFormat("en", { maximumFractionDigits: 3 }).format(
      value,
    );
  return String(value);
}
function Chart({ data }: { data: Samples | null }) {
  if (!data?.values?.length)
    return (
      <div className="chart-empty">
        Select a time-dependent signal to inspect original samples.
      </div>
    );
  const vals = data.values.map(Number).filter(Number.isFinite);
  if (!vals.length)
    return (
      <div className="chart-empty">
        No finite values available in this display window.
      </div>
    );
  const min = Math.min(...vals),
    max = Math.max(...vals),
    span = max - min || 1;
  const points = vals
    .map(
      (v, i) =>
        `${(i / Math.max(1, vals.length - 1)) * 1000},${180 - ((v - min) / span) * 155}`,
    )
    .join(" ");
  const ticks = [0, 1, 2, 3];
  return (
    <div className="plot-wrap">
      <svg
        className="plot"
        viewBox="0 0 1000 210"
        role="img"
        aria-label="Signal trace showing source samples"
      >
        <defs>
          <linearGradient id="trace" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#65ddca" stopOpacity=".18" />
            <stop offset="1" stopColor="#65ddca" stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((i) => (
          <g key={i}>
            <line
              x1="0"
              x2="1000"
              y1={25 + i * 50}
              y2={25 + i * 50}
              className="gridline"
            />
            <text x="0" y={21 + i * 50} className="plot-label">
              {format(max - (i * (max - min)) / 3)}
            </text>
          </g>
        ))}
        <polygon points={`0,180 ${points} 1000,180`} fill="url(#trace)" />
        <polyline
          points={points}
          className="trace"
          fill="none"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="axis">
        <span>
          {data.time?.length ? `${format(data.time[0])} s` : "sample 0"}
        </span>
        <span>
          {data.display_only
            ? "display decimated · audit uses source resolution"
            : "source samples"}
        </span>
        <span>
          {data.time?.length
            ? `${format(data.time.at(-1))} s`
            : `sample ${data.values.length - 1}`}
        </span>
      </div>
    </div>
  );
}
function EquilibriumMap({ data }: { data: Equilibrium | null }) {
  if (!data)
    return (
      <div className="map-empty">
        Select a catalog shot to load its verified R–Z flux frame.
      </div>
    );
  const finite = data.psi
    .flat()
    .filter((v): v is number => v !== null && Number.isFinite(v));
  if (!finite.length || !data.r.length || !data.z.length)
    return (
      <div className="map-empty">
        The source frame has no finite flux cells or coordinate axes.
      </div>
    );
  const min = Math.min(...finite),
    max = Math.max(...finite),
    span = max - min || 1,
    palette = [
      "#440154",
      "#443983",
      "#31688e",
      "#21918c",
      "#35b779",
      "#90d743",
      "#fde725",
    ];
  const color = (v: number | null) => {
    if (v === null || !Number.isFinite(v)) return "url(#missing)";
    const t =
      Math.max(0, Math.min(0.999, (v - min) / span)) * (palette.length - 1);
    const i = Math.floor(t),
      f = t - i;
    const a = palette[i],
      b = palette[i + 1];
    const rgb = (c: string) => [
      parseInt(c.slice(1, 3), 16),
      parseInt(c.slice(3, 5), 16),
      parseInt(c.slice(5, 7), 16),
    ];
    const ca = rgb(a),
      cb = rgb(b);
    return `rgb(${ca.map((n, j) => Math.round(n + (cb[j] - n) * f)).join(",")})`;
  };
  const W = 680,
    H = 420,
    L = 58,
    T = 22,
    PW = 550,
    PH = 335,
    loR = Math.min(...data.r),
    hiR = Math.max(...data.r),
    loZ = Math.min(...data.z),
    hiZ = Math.max(...data.z),
    x = (r: number) => L + ((r - loR) / (hiR - loR || 1)) * PW,
    y = (z: number) => T + PH - ((z - loZ) / (hiZ - loZ || 1)) * PH,
    cw = PW / data.r.length,
    ch = PH / data.z.length;
  const axis = data.magnetic_axis,
    axisVisible =
      !!axis &&
      axis[0] >= loR &&
      axis[0] <= hiR &&
      axis[1] >= loZ &&
      axis[1] <= hiZ;
  return (
    <div className="eqviz">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`FAIR-MAST poloidal flux map at ${data.frame_time} seconds`}
      >
        <defs>
          <pattern
            id="missing"
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" fill="#161b24" />
            <path d="M0 0V6" stroke="#3c4858" strokeWidth="2" />
          </pattern>
        </defs>
        <rect
          x={L}
          y={T}
          width={PW}
          height={PH}
          fill="#0b1119"
          stroke="#354352"
        />
        {data.psi.map((row, zi) =>
          row.map((v, ri) => (
            <rect
              key={`${zi}-${ri}`}
              x={x(data.r[ri]) - cw / 2}
              y={y(data.z[zi]) - ch / 2}
              width={cw + 0.3}
              height={ch + 0.3}
              fill={color(v)}
            />
          )),
        )}
        {Array.from({ length: 6 }, (_, i) => {
          const r = loR + ((hiR - loR) * i) / 5;
          return (
            <g key={`r${i}`}>
              <line
                x1={x(r)}
                x2={x(r)}
                y1={T}
                y2={T + PH}
                className="eq-gridline"
              />
              <text
                x={x(r)}
                y={T + PH + 19}
                textAnchor="middle"
                className="eq-label"
              >
                {r.toFixed(2)}
              </text>
            </g>
          );
        })}
        {Array.from({ length: 6 }, (_, i) => {
          const z = loZ + ((hiZ - loZ) * i) / 5;
          return (
            <g key={`z${i}`}>
              <line
                x1={L}
                x2={L + PW}
                y1={y(z)}
                y2={y(z)}
                className="eq-gridline"
              />
              <text
                x={L - 9}
                y={y(z) + 3}
                textAnchor="end"
                className="eq-label"
              >
                {z.toFixed(2)}
              </text>
            </g>
          );
        })}
        {axisVisible && (
          <g>
            <circle
              cx={x(axis![0])}
              cy={y(axis![1])}
              r="8"
              fill="none"
              stroke="#f4f5f2"
              strokeWidth="1.3"
            />
            <path
              d={`M${x(axis![0]) - 12} ${y(axis![1])}h24 M${x(axis![0])} ${y(axis![1]) - 12}v24`}
              stroke="#fff"
              strokeWidth="1"
            />
            <text
              x={x(axis![0]) + 12}
              y={y(axis![1]) - 11}
              className="eq-annotation"
            >
              magnetic axis · source
            </text>
          </g>
        )}
        <text
          x={L + PW / 2}
          y={H - 10}
          textAnchor="middle"
          className="eq-axis-title"
        >
          R [{data.r_units ?? "source units"}]
        </text>
        <text
          transform={`translate(15 ${T + PH / 2}) rotate(-90)`}
          textAnchor="middle"
          className="eq-axis-title"
        >
          Z [{data.z_units ?? "source units"}]
        </text>
        <text x={L + PW + 15} y={T + 5} className="eq-label">
          ψ [{data.psi_units ?? "source units"}]
        </text>
        <rect
          x={L + PW + 16}
          y={T + 14}
          width="12"
          height={PH - 20}
          fill="url(#viridis)"
        />
        <defs>
          <linearGradient id="viridis" x1="0" x2="0" y1="1" y2="0">
            {palette.map((c, i) => (
              <stop
                key={c}
                offset={`${(i / (palette.length - 1)) * 100}%`}
                stopColor={c}
              />
            ))}
          </linearGradient>
        </defs>
        <text x={L + PW + 33} y={T + 22} className="eq-label">
          {max.toExponential(2)}
        </text>
        <text x={L + PW + 33} y={T + PH - 2} className="eq-label">
          {min.toExponential(2)}
        </text>
      </svg>
      <div className="eq-meta">
        <span>FAIR-MAST L2 · equilibrium</span>
        <span>
          t = {data.frame_time.toFixed(4)} s · frame {data.frame_index}
        </span>
        <span>
          {data.r.length} × {data.z.length} source grid
        </span>
      </div>
    </div>
  );
}

export default function Home() {
  const [level, setLevel] = useState(2),
    [query, setQuery] = useState(""),
    [shots, setShots] = useState<Shot[]>([]),
    [loading, setLoading] = useState(false),
    [connected, setConnected] = useState(false),
    [error, setError] = useState("");
  const [selected, setSelected] = useState<number | null>(null),
    [frameIndex, setFrameIndex] = useState<number | null>(null),
    [signals, setSignals] = useState<Signal[]>([]),
    [signalName, setSignalName] = useState("ip"),
    [signalGroup, setSignalGroup] = useState("summary"),
    [auditGroup, setAuditGroup] = useState("summary"),
    [samples, setSamples] = useState<Samples | null>(null),
    [equilibrium, setEquilibrium] = useState<Equilibrium | null>(null),
    [audit, setAudit] = useState<Audit | null>(null),
    [busyAudit, setBusyAudit] = useState(false),
    [tab, setTab] = useState("workspace");
  const loadShots = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        `${API}/shots?level=${level}&limit=60&q=${encodeURIComponent(query)}`,
      );
      if (!response.ok)
        throw new Error(`${response.status} ${response.statusText}`);
      const body = await response.json();
      setShots(body.items ?? []);
      setConnected(true);
    } catch (e) {
      setConnected(false);
      setError(e instanceof Error ? e.message : "Unable to reach API");
    } finally {
      setLoading(false);
    }
  }, [level, query]);
  useEffect(() => {
    void loadShots();
  }, [loadShots]);
  useEffect(() => {
    if (!selected) return;
    let live = true;
    fetch(`${API}/shots/${selected}/signals?level=${level}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        if (live) setSignals(data);
      })
      .catch(() => {
        if (live) setSignals([]);
      });
    return () => {
      live = false;
    };
  }, [selected, level]);
  useEffect(() => {
    if (!selected || !signalName) return;
    let live = true;
    setSamples(null);
    fetch(
      `${API}/shots/${selected}/samples/${encodeURIComponent(signalName)}?group=${encodeURIComponent(signalGroup)}&level=${level}`,
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (live) setSamples(data);
      })
      .catch(() => {
        if (live) setSamples(null);
      });
    return () => {
      live = false;
    };
  }, [selected, signalName, signalGroup, level]);
  useEffect(() => {
    if (!selected) return;
    let live = true;
    setEquilibrium(null);
    const frame = frameIndex === null ? "" : `&index=${frameIndex}`;
    fetch(`${API}/shots/${selected}/equilibrium/frame?level=${level}${frame}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (live) setEquilibrium(data);
      })
      .catch(() => {
        if (live) setEquilibrium(null);
      });
    return () => {
      live = false;
    };
  }, [selected, level, frameIndex]);
  useEffect(() => {
    const id = audit?.id;
    if (!id || audit.status === "completed" || audit.status === "failed")
      return;
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const response = await fetch(`${API}/audits/${id}`);
        if (!response.ok) throw new Error("Could not retrieve audit status");
        const result: Audit = await response.json();
        if (!live) return;
        setAudit(result);
        if (result.status !== "completed" && result.status !== "failed")
          timer = setTimeout(poll, 1500);
      } catch (e) {
        if (live)
          setAudit((current) =>
            current?.id === id
              ? {
                  ...current,
                  status: "failed",
                  error:
                    e instanceof Error
                      ? e.message
                      : "Audit status request failed",
                }
              : current,
          );
      }
    };
    timer = setTimeout(poll, 750);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [audit?.id, audit?.status]);
  const selectedShot = useMemo(
    () => shots.find((s) => s.shot_id === selected),
    [shots, selected],
  );
  const auditActive = audit?.status === "queued" || audit?.status === "running";
  const startAudit = async () => {
    if (!selected) return;
    const shotId = selected;
    setBusyAudit(true);
    setAudit(null);
    try {
      const response = await fetch(
        `${API}/audits?shot_id=${shotId}&level=${level}&group=${auditGroup}`,
        { method: "POST" },
      );
      if (!response.ok)
        throw new Error(`Audit request failed (${response.status})`);
      const queued = await response.json();
      setAudit({
        id: queued.id,
        shot_id: shotId,
        status: queued.status ?? "queued",
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Audit request failed");
    } finally {
      setBusyAudit(false);
    }
  };
  const exportAudit = () => {
    if (!audit?.report) return;
    const blob = new Blob([JSON.stringify(audit.report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `mast-${audit.report.shot_id}-${auditGroup}-audit.json`;
    link.click();
    URL.revokeObjectURL(url);
  };
  const fields = selectedShot
    ? Object.entries(selectedShot)
        .filter(([k]) => k !== "shot_id")
        .slice(0, 8)
    : [];
  return (
    <main className="app-shell">
      <aside className="rail">
        <div className="brand-mark">
          <Atom size={22} />
          <span className="brand-dot" />
        </div>
        <div className="rail-rule" />
        <button
          className={`rail-button ${tab === "workspace" ? "active" : ""}`}
          onClick={() => setTab("workspace")}
          aria-label="Shot workspace"
        >
          <SquareActivity />
        </button>
        <button
          className={`rail-button ${tab === "catalog" ? "active" : ""}`}
          onClick={() => setTab("catalog")}
          aria-label="Shot catalog"
        >
          <Database />
        </button>
        <button
          className={`rail-button ${tab === "method" ? "active" : ""}`}
          onClick={() => setTab("method")}
          aria-label="Methodology"
        >
          <BookOpen />
        </button>
        <div className="rail-bottom">
          <button className="rail-button" title="Help">
            <CircleHelp />
          </button>
          <span className="avatar">PS</span>
        </div>
      </aside>
      <section className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>RESEARCH WORKSPACE</span>
            <span className="slash">/</span>
            <strong>
              {tab === "method"
                ? "Methodology"
                : tab === "catalog"
                  ? "Shot catalog"
                  : "Discharge inspection"}
            </strong>
          </div>
          <div className="top-actions">
            <div className={`connection ${connected ? "online" : "offline"}`}>
              <i />
              {connected ? "Catalog connected" : "API unavailable"}
            </div>
            <a
              className="docs-link"
              href="https://ukaea.github.io/fair-mast/quickstart.html"
              target="_blank"
              rel="noreferrer"
            >
              FAIR-MAST docs <ExternalLink size={12} />
            </a>
          </div>
        </header>
        {tab === "method" ? (
          <div className="method-page">
            <div className="eyebrow">SCIENTIFIC METHOD</div>
            <h1>Trust is built from provenance.</h1>
            <p className="lede">
              Shot Inspector reads archival values without silently changing
              them. Every rule reports what it examined, what it could not
              evaluate, and the source context behind its result.
            </p>
            <div className="method-grid">
              <article>
                <span>01 / SOURCE</span>
                <h2>Separate source levels</h2>
                <p>
                  FAIR-MAST Level 1 and Level 2 remain independent. Level 2 may
                  include cropping, interpolation and calibration. Group
                  metadata can expose ingestion commit and release context.
                </p>
              </article>
              <article>
                <span>02 / EVIDENCE</span>
                <h2>No inferred passes</h2>
                <p>
                  Missing prerequisites yield NOT_EVALUATED. Negative
                  pre-trigger timestamps are not inherently invalid. Statistical
                  outliers are review candidates, never automatic
                  instrument-fault declarations.
                </p>
              </article>
              <article>
                <span>03 / DISPLAY</span>
                <h2>Display is not analysis</h2>
                <p>
                  Large one-dimensional traces may be decimated for rendering.
                  Validation evaluates the loaded source arrays at their
                  original resolution.
                </p>
              </article>
            </div>
            <div className="source-note">
              <strong>Current implementation boundary</strong>
              <p>
                Operational source: FAIR-MAST Level 1 and Level 2 metadata plus
                selective Zarr groups. Sophelio, local-file ingestion,
                equilibrium topology extraction, complete export formats and
                browser-side playback are not yet implemented.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="page-heading">
              <div>
                <div className="eyebrow">
                  PLASMA SHOT INSPECTOR <span>·</span> EXPERIMENTAL INTEGRITY.
                  EQUILIBRIUM CONFIDENCE.
                </div>
                <h1>Discharge inspection</h1>
                <p>
                  Trace experimental measurements back to the source. Audit what
                  can be checked.
                </p>
              </div>
              <div className="heading-actions">
                <button
                  className="quiet-button"
                  onClick={() => void loadShots()}
                >
                  <ArrowDownUp size={15} /> Refresh catalog
                </button>
                <button
                  className="primary-button"
                  onClick={() => void startAudit()}
                  disabled={!selected || busyAudit || auditActive}
                >
                  {busyAudit || auditActive ? (
                    <LoaderCircle size={15} className="spin" />
                  ) : (
                    <ShieldCheck size={15} />
                  )}{" "}
                  {busyAudit || auditActive ? "Auditing source…" : "Run audit"}
                </button>
              </div>
            </div>
            {error && (
              <div className="banner error-banner">
                <AlertCircle size={16} />
                <span>
                  {error}. Start the local API with <code>make dev</code>, then
                  refresh.
                </span>
                <button onClick={() => setError("")}>
                  <X size={15} />
                </button>
              </div>
            )}
            <div className="workspace-grid">
              <section className="panel catalog-panel">
                <div className="panel-head">
                  <div>
                    <div className="panel-title">
                      <Database size={15} /> SHOT CATALOG
                    </div>
                    <div className="panel-sub">FAIR-MAST · public metadata</div>
                  </div>
                  <button className="icon-button" aria-label="Catalog filters">
                    <SlidersHorizontal size={15} />
                  </button>
                </div>
                <div className="catalog-tools">
                  <label className="searchbox">
                    <Search size={14} />
                    <input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Search shot, metadata…"
                    />
                    <kbd>/</kbd>
                  </label>
                  <button
                    className="source-select"
                    onClick={() => setLevel(level === 1 ? 2 : 1)}
                    title="Switch dataset level"
                  >
                    L{level}
                    <ChevronDown size={13} />
                  </button>
                </div>
                <div className="catalog-meta">
                  <span>
                    {loading
                      ? "Reading remote catalog…"
                      : `${shots.length} catalog rows`}
                  </span>
                  <span>
                    <span className="live-dot" /> SOURCE INDEX
                  </span>
                </div>
                <div className="shot-list">
                  {shots.map((s, i) => (
                    <button
                      key={`${s.shot_id}-${i}`}
                      className={`shot-row ${selected === s.shot_id ? "selected" : ""}`}
                      onClick={() => {
                        setSelected(s.shot_id);
                        setAudit(null);
                        setSignalName("ip");
                      }}
                    >
                      <span className="shot-state">
                        <Activity size={14} />
                      </span>
                      <span className="shot-main">
                        <strong>
                          MAST <b>{s.shot_id}</b>
                        </strong>
                        <small>
                          {format(
                            s.description ??
                              s.pulse_type ??
                              s.campaign ??
                              "FAIR-MAST catalog entry",
                          )}
                        </small>
                      </span>
                      <span className="shot-level">L{level}</span>
                      <ArrowRight size={13} className="row-arrow" />
                    </button>
                  ))}
                  {!loading && !shots.length && (
                    <div className="empty-catalog">
                      {error
                        ? "Catalog is unreachable"
                        : "No catalog rows match this query"}
                    </div>
                  )}
                </div>
                <div className="catalog-footer">
                  <span>
                    <span className="green-dot" /> Official source
                  </span>
                  <span>
                    Page 1 <ArrowRight size={11} />
                  </span>
                </div>
              </section>
              <section className="center-column">
                <section className="panel identity-panel">
                  <div className="identity-top">
                    <div>
                      <div className="panel-title">
                        <Radio size={15} /> SHOT IDENTITY
                      </div>
                      <div className="identity-number">
                        {selected ? (
                          <>
                            <span>MAST</span> {selected}
                          </>
                        ) : (
                          <span className="placeholder">
                            Select a catalog shot
                          </span>
                        )}
                      </div>
                    </div>
                    <span className="source-pill">
                      <span className="green-dot" />{" "}
                      {selected ? `FAIR-MAST L${level}` : "AWAITING SHOT"}
                    </span>
                  </div>
                  <div className="identity-metadata">
                    {fields.map(([key, val]) => (
                      <div key={key}>
                        <span>{key.replaceAll("_", " ")}</span>
                        <strong>{format(val)}</strong>
                      </div>
                    ))}
                  </div>
                </section>
                <section className="panel equilibrium-panel">
                  <div className="panel-head">
                    <div>
                      <div className="panel-title">
                        <Layers2 size={15} /> EQUILIBRIUM · POLOIDAL FLUX
                      </div>
                      <div className="panel-sub">
                        Explicit R–Z dimensions · source order preserved
                      </div>
                    </div>
                    <span className="muted-chip">
                      {equilibrium
                        ? `t ${equilibrium.frame_time.toFixed(4)} s`
                        : "LOADING SOURCE"}
                    </span>
                  </div>
                  <EquilibriumMap data={equilibrium} />
                  {equilibrium && (
                    <div className="frame-control">
                      <span>{equilibrium.frame_selection}</span>
                      <label htmlFor="frame-index">
                        Frame {equilibrium.frame_index} /{" "}
                        {equilibrium.frame_count - 1}
                      </label>
                      <input
                        id="frame-index"
                        aria-label="Equilibrium frame index"
                        type="range"
                        min={0}
                        max={equilibrium.frame_count - 1}
                        value={equilibrium.frame_index}
                        onChange={(e) => setFrameIndex(Number(e.target.value))}
                      />
                    </div>
                  )}
                </section>
                <section className="panel signal-panel">
                  <div className="panel-head">
                    <div>
                      <div className="panel-title">
                        <Activity size={15} /> SIGNAL EXPLORER
                      </div>
                      <div className="panel-sub">
                        Source group <b>{signalGroup}</b> · values are not
                        repaired
                      </div>
                    </div>
                    <div className="signal-select-wrap">
                      <select
                        value={signalName}
                        onChange={(e) => {
                          const next = signals.find(
                            (s) => s.name === e.target.value,
                          );
                          setSignalName(e.target.value);
                          if (next?.source) setSignalGroup(next.source);
                        }}
                        disabled={!selected}
                      >
                        <option value="ip">ip · summary</option>
                        {signals
                          .filter(
                            (s) =>
                              s.dimensions?.length === 1 &&
                              s.dimensions[0] === "time",
                          )
                          .map((s) => (
                            <option
                              key={`${s.source}-${s.name}`}
                              value={s.name}
                            >
                              {s.name} · {s.source}
                            </option>
                          ))}
                      </select>
                      <ChevronDown size={12} />
                    </div>
                  </div>
                  <div className="chart-title">
                    <strong>{signalName}</strong>
                    <span>
                      {samples?.units ??
                        (signalName === "ip" ? "source units" : "")}
                    </span>
                    <span className="display-chip">LIVE SOURCE</span>
                  </div>
                  <Chart data={samples} />
                  <div className="chart-legend">
                    <span>
                      <i className="legend-line" /> {signalName}{" "}
                      <b>{samples?.units ?? ""}</b>
                    </span>
                    <span>
                      {samples?.values?.length
                        ? `${samples.values.length.toLocaleString()} display points`
                        : "No samples loaded"}
                    </span>
                  </div>
                </section>
                <section className="panel timeline-panel">
                  <div className="panel-head">
                    <div>
                      <div className="panel-title">
                        <Gauge size={15} /> DISCHARGE CONTEXT
                      </div>
                      <div className="panel-sub">
                        Use source coordinates and intervals as published
                      </div>
                    </div>
                    <span className="muted-chip">STATIC VIEW</span>
                  </div>
                  <div className="context-strip">
                    <div>
                      <span className="context-icon">
                        <Layers2 size={15} />
                      </span>
                      <span>
                        <strong>Source values preserved</strong>
                        <small>Validation does not use display reduction</small>
                      </span>
                    </div>
                    <div>
                      <span className="context-icon mint">
                        <ShieldCheck size={15} />
                      </span>
                      <span>
                        <strong>Evidence-linked rules</strong>
                        <small>
                          Every finding includes rule ID and evidence
                        </small>
                      </span>
                    </div>
                    <div>
                      <span className="context-icon amber">
                        <CircleHelp size={15} />
                      </span>
                      <span>
                        <strong>Partial capability</strong>
                        <small>Unavailable physics is marked unevaluated</small>
                      </span>
                    </div>
                  </div>
                  <div className="time-track">
                    <div className="time-head">
                      <span>OBSERVED TIME AXIS</span>
                      <span>
                        {samples?.time?.length
                          ? `${format(samples.time[0])} — ${format(samples.time.at(-1))} s`
                          : "—"}
                      </span>
                    </div>
                    <div className="track">
                      <span className="track-fill" />
                      <i />
                    </div>
                    <div className="track-labels">
                      <span>PRE-TRIGGER</span>
                      <span>SHOT INTERVAL</span>
                      <span>END</span>
                    </div>
                  </div>
                </section>
              </section>
              <aside className="right-column">
                <section className="panel integrity-panel">
                  <div className="panel-head">
                    <div>
                      <div className="panel-title">
                        <ShieldCheck size={15} /> AUDIT INTEGRITY
                      </div>
                      <div className="panel-sub">
                        Evidence summary · v1 rules
                      </div>
                    </div>
                    <span
                      className={`audit-status ${audit?.status === "completed" ? "status-done" : ""}`}
                    >
                      {audit?.status === "completed"
                        ? "COMPLETE"
                        : busyAudit || auditActive
                          ? "RUNNING"
                          : audit?.status === "failed"
                            ? "FAILED"
                            : "READY"}
                    </span>
                  </div>
                  <div className="audit-controls">
                    <label>
                      GROUP{" "}
                      <select
                        value={auditGroup}
                        onChange={(e) => setAuditGroup(e.target.value)}
                      >
                        <option value="summary">summary</option>
                        <option value="equilibrium">equilibrium</option>
                        <option value="magnetics">magnetics</option>
                        <option value="thomson_scattering">
                          thomson_scattering
                        </option>
                      </select>
                    </label>
                    {audit?.report && (
                      <button onClick={exportAudit}>
                        <Download size={13} /> JSON
                      </button>
                    )}
                  </div>
                  <div className="integrity-score">
                    <span className="score-icon">
                      <ShieldCheck size={21} />
                    </span>
                    <div>
                      <strong>
                        {audit
                          ? audit.status === "completed"
                            ? (audit.report?.findings.filter(
                                (f) => f.outcome === "FAIL",
                              ).length ?? 0)
                            : "…"
                          : "—"}
                      </strong>
                      <small>{audit ? "failed checks" : "No audit run"}</small>
                    </div>
                    <span className="score-caption">
                      {audit?.status === "completed"
                        ? `${audit.report?.rules_evaluated} evaluated`
                        : "Select shot to begin"}
                    </span>
                  </div>
                  <div className="integrity-bar">
                    <i
                      style={{
                        width:
                          audit?.status === "completed"
                            ? `${Math.max(4, (100 * (audit.report?.rules_evaluated ?? 0)) / Math.max(1, (audit.report?.rules_evaluated ?? 0) + (audit.report?.rules_not_evaluated ?? 0)))}%`
                            : "0%",
                      }}
                    />
                  </div>
                  <div className="audit-metrics">
                    <div>
                      <span>RULES EVALUATED</span>
                      <b>{audit?.report?.rules_evaluated ?? "—"}</b>
                    </div>
                    <div>
                      <span>NOT EVALUATED</span>
                      <b>{audit?.report?.rules_not_evaluated ?? "—"}</b>
                    </div>
                  </div>
                  {audit?.error && (
                    <p className="inline-error">{audit.error}</p>
                  )}
                </section>
                <section className="panel findings-panel">
                  <div className="panel-head">
                    <div>
                      <div className="panel-title">
                        <FileSearch size={15} /> FINDINGS
                      </div>
                      <div className="panel-sub">
                        Source-backed validation results
                      </div>
                    </div>
                    <button className="icon-button" title="Findings">
                      <Filter size={14} />
                    </button>
                  </div>
                  <div className="findings-list">
                    {audit?.report?.findings?.length ? (
                      audit.report.findings.slice(0, 7).map((f, i) => (
                        <article className="finding" key={`${f.rule_id}-${i}`}>
                          <span
                            className={`finding-mark ${f.outcome.toLowerCase()}`}
                          >
                            {f.outcome === "PASS" ? (
                              <Check size={12} />
                            ) : f.outcome === "NOT_EVALUATED" ? (
                              <CircleHelp size={12} />
                            ) : (
                              <AlertCircle size={12} />
                            )}
                          </span>
                          <div>
                            <strong>{f.summary}</strong>
                            <p>{f.explanation}</p>
                            <code>{f.rule_id}</code>
                          </div>
                          <span
                            className={`severity ${f.severity.toLowerCase()}`}
                          >
                            {f.severity}
                          </span>
                        </article>
                      ))
                    ) : (
                      <div className="findings-empty">
                        <span className="empty-orbit">
                          <Sparkles size={17} />
                        </span>
                        <strong>
                          {selected ? "Ready to inspect" : "No shot selected"}
                        </strong>
                        <p>
                          {selected
                            ? "Run an audit to evaluate the selected source group."
                            : "Choose a real shot from the catalog to see metadata and signals."}
                        </p>
                      </div>
                    )}
                  </div>
                  {audit?.report?.limitations.map((l, i) => (
                    <div className="limitation" key={i}>
                      <CircleHelp size={12} />
                      {l}
                    </div>
                  ))}
                </section>
                <div className="provenance-card">
                  <div>
                    <span className="provenance-dot" />
                    <strong>PROVENANCE FIRST</strong>
                  </div>
                  <p>
                    FAIR-MAST release paths can be mutable. Inspect ingestion
                    metadata before reproducing an audit.
                  </p>
                  <a
                    href="https://ukaea.github.io/fair-mast/level2/release-history.html"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Release history <ArrowRight size={12} />
                  </a>
                </div>
              </aside>
            </div>
            <footer className="app-footer">
              <span>
                PLASMA SHOT INSPECTOR <b>0.1.0</b>
              </span>
              <span>
                READ-ONLY SOURCE ACCESS · FAIR-MAST <i>•</i>{" "}
                <a onClick={() => setTab("method")}>METHODOLOGY</a>
              </span>
              <span>BUILD FOR SCIENTIFIC TRACEABILITY</span>
            </footer>
          </>
        )}
      </section>
    </main>
  );
}
