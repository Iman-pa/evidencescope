import { useState, useCallback, useRef } from "react";
import { callAnalyze, callOverride, callCompare } from "./api.js";

// ---------------------------------------------------------------------------
// EvidenceScope — evidence-linked MCDA for health technology review
// Design: paper background, Source Serif 4 / IBM Plex font pairing,
// teal = AI-suggested, amber = human-overridden. Preserved from prototype.
// ---------------------------------------------------------------------------

const CRITERIA = [
  { key: "clinical_benefit",   label: "Clinical Benefit",    hint: "Comparative effectiveness vs. current standard of care" },
  { key: "safety",             label: "Safety",              hint: "Harms, adverse events, tolerability" },
  { key: "cost_effectiveness", label: "Cost-Effectiveness",  hint: "Cost per unit of health benefit (e.g., cost/QALY)" },
  { key: "budget_impact",      label: "Budget Impact",       hint: "Net effect on payer budget if adopted" },
  { key: "equity_access",      label: "Equity & Access",     hint: "Effect on underserved or high-need populations" },
  { key: "feasibility",        label: "Feasibility",         hint: "Practicality of delivering/implementing the technology" },
];

// Convert backend [0,1] normalized weighted score to [1,9] display scale.
// Algebraically equivalent to Σ(wᵢ/Σw)·sᵢ — matches prototype's display formula.
function toDisplayScore(backendVal) {
  return (backendVal * 8 + 1).toFixed(2);
}

export default function EvidenceScope() {
  const [phase, setPhase] = useState("idle"); // idle | uploading | done | error
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const [analysisId, setAnalysisId]         = useState(null);
  const [criteriaResults, setCriteriaResults] = useState(null);
  const [currentScores, setCurrentScores]   = useState({});
  const [currentWeights, setCurrentWeights] = useState(
    // Use Math.round so slider display (which also rounds) matches stored value.
    // Math.round(100/6) = 17 each → sum 102, honest: "normalized automatically".
    Object.fromEntries(CRITERIA.map((c) => [c.key, Math.round(100 / CRITERIA.length)]))
  );
  const [weightedScore, setWeightedScore]   = useState(null); // [0,1] from server
  const [auditTrail, setAuditTrail]         = useState([]);
  const [aiSuggestedScores, setAiSuggestedScores] = useState({});
  const [overrideSet, setOverrideSet]       = useState(new Set());
  const [expanded, setExpanded]             = useState(null);
  const [errorMsg, setErrorMsg]             = useState("");
  const [analysisLabel, setAnalysisLabel]   = useState("");

  // Saved analyses for cross-drug comparison
  const [savedAnalyses, setSavedAnalyses]   = useState([]); // [{id, label, scores, weights}]
  const [compareResult, setCompareResult]   = useState(null);
  const [showCompare, setShowCompare]       = useState(false);
  const [compareError, setCompareError]     = useState("");

  // -------------------------------------------------------------------------
  // File selection
  // -------------------------------------------------------------------------

  const applyFiles = (files) => {
    const pdfs = Array.from(files).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdfs.length === 0) {
      setErrorMsg("Please select PDF files.");
      return;
    }
    setSelectedFiles(pdfs);
    setErrorMsg("");
  };

  const handleFileInput = (e) => applyFiles(e.target.files);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    applyFiles(e.dataTransfer.files);
  };

  // -------------------------------------------------------------------------
  // POST /analyze
  // -------------------------------------------------------------------------

  const handleAnalyze = useCallback(async () => {
    if (selectedFiles.length === 0) {
      setErrorMsg("Select at least one PDF before running analysis.");
      return;
    }
    setPhase("uploading");
    setErrorMsg("");
    setCriteriaResults(null);
    setAnalysisId(null);
    setAuditTrail([]);
    setAiSuggestedScores({});
    setOverrideSet(new Set());
    setCompareResult(null);
    setCompareError("");

    try {
      const data = await callAnalyze(selectedFiles);

      setAnalysisId(data.analysis_id);
      setAnalysisLabel(data.label || "");
      setCriteriaResults(data.criteria_results);
      setCurrentScores(data.current_scores);
      setAiSuggestedScores(data.current_scores);
      // Backend now initialises weights at 100/N each (same percentage scale).
      // Round to integers so slider display matches stored value exactly —
      // prevents the mismatch where slider showed 17 but stored value was 16.667,
      // causing the next slider interaction to send 17 vs 1.0 for other criteria.
      const totalW = Object.values(data.current_weights).reduce((a, b) => a + b, 0);
      const pctWeights = Object.fromEntries(
        CRITERIA.map((c) => [c.key, Math.round((data.current_weights[c.key] / totalW) * 100)])
      );
      setCurrentWeights(pctWeights);
      setWeightedScore(data.initial_weighted_score);
      setPhase("done");
    } catch (err) {
      setErrorMsg(err.message || "Something went wrong analysing this report.");
      setPhase("error");
    }
  }, [selectedFiles]);

  // -------------------------------------------------------------------------
  // Slider handlers — optimistic local update, server commit on pointer-up
  // Note: weight slider min is 1 (not 0) because the backend rejects new_value ≤ 0.
  // -------------------------------------------------------------------------

  const handleScoreChange = (key, val) => {
    setCurrentScores((prev) => ({ ...prev, [key]: val }));
  };

  const handleScoreCommit = async (key, val) => {
    if (!analysisId) return;
    try {
      const data = await callOverride({
        analysisId,
        criterionKey: key,
        field: "score",
        newValue: val,
      });
      setWeightedScore(data.updated_weighted_score);
      setAuditTrail(data.audit_trail);
      setOverrideSet((prev) => new Set([...prev, key]));
    } catch (err) {
      setErrorMsg(`Override failed: ${err.message}`);
    }
  };

  const handleWeightChange = (key, val) => {
    setCurrentWeights((prev) => ({ ...prev, [key]: val }));
  };

  const handleWeightCommit = async (key, val) => {
    if (!analysisId) return;
    try {
      const data = await callOverride({
        analysisId,
        criterionKey: key,
        field: "weight",
        newValue: val,
      });
      setWeightedScore(data.updated_weighted_score);
      setAuditTrail(data.audit_trail);
      setOverrideSet((prev) => new Set([...prev, key + "_weight"]));
    } catch (err) {
      setErrorMsg(`Override failed: ${err.message}`);
    }
  };

  const totalWeight = Object.values(currentWeights).reduce((a, b) => a + Number(b), 0);

  // -------------------------------------------------------------------------
  // Save current analysis for cross-drug comparison
  // -------------------------------------------------------------------------

  const handleSaveForComparison = () => {
    if (!analysisId || !criteriaResults) return;
    const label = analysisLabel || analysisId.slice(0, 8);
    // Avoid duplicate saves
    if (savedAnalyses.some((a) => a.id === analysisId)) return;
    setSavedAnalyses((prev) => [
      ...prev,
      { id: analysisId, label, scores: { ...currentScores }, weights: { ...currentWeights } },
    ]);
  };

  const handleCompare = useCallback(async () => {
    if (savedAnalyses.length < 2) return;
    setCompareError("");
    try {
      const result = await callCompare(
        savedAnalyses.map((a) => ({ analysis_id: a.id, label: a.label }))
      );
      setCompareResult(result);
      setShowCompare(true);
    } catch (err) {
      setCompareError(`Comparison failed: ${err.message}`);
    }
  }, [savedAnalyses]);

  // -------------------------------------------------------------------------
  // Export scorecard (uses server audit trail)
  // -------------------------------------------------------------------------

  const exportReport = () => {
    if (!criteriaResults) return;
    const displayWS = weightedScore !== null ? toDisplayScore(weightedScore) : "—";
    let md = `# EvidenceScope Scorecard\n\nGenerated: ${new Date().toLocaleString()}\n\n`;
    md += `**Overall weighted score:** ${displayWS} / 9\n\n`;
    md += `| Criterion | Weight | Score | Evidence | Citation |\n|---|---|---|---|---|\n`;
    CRITERIA.forEach((c) => {
      const r = criteriaResults[c.key] || {};
      md += `| ${c.label} | ${Math.round(currentWeights[c.key])}% | ${currentScores[c.key]} | ${(r.evidence || "").replace(/\|/g, "/")} | ${r.citation || "n/a"} |\n`;
    });
    // Verification flags
    const flaggedCriteria = CRITERIA.filter((c) => criteriaResults[c.key]?.verification_flag);
    if (flaggedCriteria.length > 0) {
      md += `\n## Verification Flags (score–evidence mismatches detected by AI)\n\n`;
      flaggedCriteria.forEach((c) => {
        const r = criteriaResults[c.key];
        md += `- **${c.label}**: ${r.verification_note || "score may not match evidence"}\n`;
      });
    }
    if (auditTrail.length > 0) {
      md += `\n## Audit Trail (human overrides)\n\n`;
      auditTrail.forEach((entry) => {
        const label = CRITERIA.find((c) => c.key === entry.criterion_key)?.label || entry.criterion_key;
        md += `- **${label}** (${entry.field}): ${entry.old_value} → ${entry.new_value} at ${entry.changed_at}\n`;
      });
    }
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "evidencescope-scorecard.md";
    a.click();
    URL.revokeObjectURL(url);
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div style={styles.page}>
      <style>{fontImports}</style>

      <header style={styles.header}>
        <div style={styles.headerInner}>
          <div>
            <div style={styles.eyebrow}>EVIDENCE-LINKED MCDA · HEALTH TECHNOLOGY REVIEW</div>
            <h1 style={styles.title}>EvidenceScope</h1>
            <p style={styles.subtitle}>
              Every score traces back to evidence, or to a documented human decision. Nothing in between.
            </p>
          </div>
          <div style={styles.scoreBadge}>
            <div style={styles.scoreBadgeLabel}>Weighted Score</div>
            <div style={styles.scoreBadgeValue}>
              {weightedScore !== null ? toDisplayScore(weightedScore) : "—"}
              <span style={styles.scoreBadgeMax}> / 9</span>
            </div>
          </div>
        </div>
      </header>

      <main style={styles.main}>
        {/* ---------------------------------------------------------------- */}
        {/* 01 — SOURCE DOCUMENT                                             */}
        {/* ---------------------------------------------------------------- */}
        <section style={styles.inputPanel}>
          <div style={styles.panelLabel}>01 — SOURCE DOCUMENT</div>

          {/* Drop zone */}
          <div
            style={{
              ...styles.dropZone,
              ...(isDragOver ? styles.dropZoneActive : {}),
            }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              style={{ display: "none" }}
              onChange={handleFileInput}
            />
            {selectedFiles.length === 0 ? (
              <>
                <div style={styles.dropZoneIcon}>↑</div>
                <div style={styles.dropZoneText}>
                  Click to select PDFs, or drag and drop here
                </div>
                <div style={styles.dropZoneHint}>
                  Upload the combined HTA report and any supporting documents
                </div>
              </>
            ) : (
              <>
                <div style={styles.dropZoneIcon}>✓</div>
                <div style={styles.dropZoneText}>
                  {selectedFiles.length === 1
                    ? selectedFiles[0].name
                    : `${selectedFiles.length} files selected`}
                </div>
                {selectedFiles.length > 1 && (
                  <div style={styles.dropZoneHint}>
                    {selectedFiles.map((f) => f.name).join(" · ")}
                  </div>
                )}
              </>
            )}
          </div>

          <div style={styles.inputRow}>
            <button
              style={{ ...styles.primaryButton, opacity: phase === "uploading" ? 0.6 : 1 }}
              onClick={handleAnalyze}
              disabled={phase === "uploading"}
            >
              {phase === "uploading" ? "Extracting evidence…" : "Analyze report"}
            </button>
            <button
              style={styles.ghostButton}
              onClick={() => { setSelectedFiles([]); if (fileInputRef.current) fileInputRef.current.value = ""; }}
              disabled={phase === "uploading"}
            >
              Clear
            </button>
          </div>

          {(phase === "error" || errorMsg) && (
            <div style={styles.errorBox}>{errorMsg}</div>
          )}

          <div style={styles.noteBox}>
            Upload one or more PDFs for a single HTA review (e.g., combined report + patient input).
            Text is extracted and sent to the backend — no content leaves your session.
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* 02 — SCORECARD                                                   */}
        {/* ---------------------------------------------------------------- */}
        <section style={styles.resultsPanel}>
          <div style={styles.panelLabel}>02 — SCORECARD</div>

          {!criteriaResults && phase !== "uploading" && (
            <div style={styles.emptyState}>
              Upload a PDF and run the analysis to populate the scorecard.
            </div>
          )}

          {phase === "uploading" && (
            <div style={styles.emptyState}>
              <div style={{ marginBottom: "8px", fontSize: "14px", color: TEAL, fontWeight: 500 }}>
                Reading document and extracting evidence…
              </div>
              <div style={{ fontSize: "12px", color: "#9A9A8E" }}>
                This typically takes 60–90 seconds. The model is reading each page and scoring all six criteria.
              </div>
            </div>
          )}

          {criteriaResults &&
            CRITERIA.map((c) => {
              const r = criteriaResults[c.key] || {};
              const isOverridden = overrideSet.has(c.key);
              const isOpen = expanded === c.key;
              const criterionTrail = auditTrail.filter(
                (e) => e.criterion_key === c.key && e.field === "score"
              );

              return (
                <div key={c.key} style={styles.criterionCard}>
                  <div
                    style={styles.criterionHeaderRow}
                    onClick={() => setExpanded(isOpen ? null : c.key)}
                  >
                    <div>
                      <div style={styles.criterionLabel}>{c.label}</div>
                      <div style={styles.criterionHint}>{c.hint}</div>
                    </div>
                    <div style={styles.criterionScoreCluster}>
                      {r.verification_flag && (
                        <span
                          style={styles.verificationFlag}
                          title={r.verification_note || "Score may not match evidence"}
                        >
                          ⚑ review
                        </span>
                      )}
                      <span
                        style={{
                          ...styles.confidenceTag,
                          ...(r.confidence === "low" ? styles.confidenceLow : {}),
                        }}
                      >
                        {r.confidence || "n/a"}
                      </span>
                      <span style={isOverridden ? styles.scorePillOverridden : styles.scorePillAI}>
                        {currentScores[c.key] ?? "—"}
                      </span>
                    </div>
                  </div>

                  {isOpen && (
                    <div style={styles.criterionBody}>
                      <p style={styles.evidenceText}>{r.evidence || "No evidence extracted."}</p>
                      <div style={styles.citationStub}>SOURCE: {r.citation || "n/a"}</div>
                      <p style={styles.rationaleText}>{r.rationale}</p>

                      <div style={styles.sliderRow}>
                        <label style={styles.sliderLabel}>Score (1–9)</label>
                        <input
                          type="range"
                          min="1"
                          max="9"
                          step="1"
                          value={currentScores[c.key] ?? 5}
                          onChange={(e) => handleScoreChange(c.key, Number(e.target.value))}
                          onPointerUp={(e) => handleScoreCommit(c.key, Number(e.target.value))}
                          style={styles.slider}
                        />
                        <span style={styles.sliderValue}>{currentScores[c.key]}</span>
                      </div>

                      <div style={styles.sliderRow}>
                        <label style={styles.sliderLabel}>Weight (%)</label>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          step="1"
                          value={Math.round(currentWeights[c.key])}
                          onChange={(e) => handleWeightChange(c.key, Number(e.target.value))}
                          onPointerUp={(e) => handleWeightCommit(c.key, Number(e.target.value))}
                          style={styles.slider}
                        />
                        <span style={styles.sliderValue}>
                          {totalWeight > 0
                            ? (currentWeights[c.key] / totalWeight * 100).toFixed(1)
                            : "0.0"}%
                        </span>
                      </div>

                      {r.verification_flag && r.verification_note && (
                        <div style={styles.verificationNote}>
                          ⚑ {r.verification_note}
                        </div>
                      )}
                      {aiSuggestedScores[c.key] !== undefined && (
                        <div style={styles.aiSuggestionNote}>
                          AI suggestion: {aiSuggestedScores[c.key]}
                        </div>
                      )}
                      {criterionTrail.map((entry, i) => (
                        <div key={i} style={styles.overrideNote}>
                          Override {i + 1}: {entry.old_value} → {entry.new_value} at{" "}
                          {new Date(entry.changed_at).toLocaleTimeString()}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

          {criteriaResults && (
            <div style={styles.footerRow}>
              <div style={styles.weightTotal}>
                Weights normalized to 100% for scoring
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  style={{
                    ...styles.ghostButton,
                    fontSize: "12px",
                    padding: "8px 14px",
                    opacity: savedAnalyses.some((a) => a.id === analysisId) ? 0.45 : 1,
                  }}
                  onClick={handleSaveForComparison}
                  disabled={savedAnalyses.some((a) => a.id === analysisId)}
                  title="Save this analysis to compare against others"
                >
                  {savedAnalyses.some((a) => a.id === analysisId) ? "Saved" : "Save for comparison"}
                </button>
                <button style={styles.exportButton} onClick={exportReport}>
                  Export scorecard (.md)
                </button>
              </div>
            </div>
          )}

          {/* Cross-drug comparison panel */}
          {savedAnalyses.length >= 2 && (
            <div style={{ marginTop: "20px", borderTop: `1px solid ${LINE}`, paddingTop: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", letterSpacing: "0.1em", color: "#9A9A8E" }}>
                  03 — CROSS-DRUG COMPARISON ({savedAnalyses.length} saved)
                </div>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  {savedAnalyses.map((a) => (
                    <span key={a.id} style={{ fontSize: "11px", color: TEAL, fontFamily: "'IBM Plex Mono', monospace", background: TEAL_DIM, padding: "2px 8px", borderRadius: "3px" }}>
                      {a.label}
                    </span>
                  ))}
                  <button style={{ ...styles.primaryButton, fontSize: "12px", padding: "7px 14px" }} onClick={handleCompare}>
                    Run comparison
                  </button>
                  <button style={{ ...styles.ghostButton, fontSize: "12px", padding: "7px 10px" }} onClick={() => { setSavedAnalyses([]); setCompareResult(null); setShowCompare(false); }}>
                    Clear
                  </button>
                </div>
              </div>

              {compareError && <div style={styles.errorBox}>{compareError}</div>}

              {showCompare && compareResult && (
                <div>
                  {/* Overall ranking */}
                  <div style={{ marginBottom: "10px" }}>
                    {compareResult.ranking.map((item) => (
                      <div key={item.analysis_id} style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", color: "#9A9A8E", width: "20px" }}>#{item.rank}</span>
                        <span style={{ fontWeight: 600, fontSize: "13px", minWidth: "120px" }}>{item.label}</span>
                        <div style={{ flex: 1, background: LINE, borderRadius: "3px", height: "8px" }}>
                          <div style={{ width: `${(item.topsis_score * 100).toFixed(1)}%`, background: TEAL, height: "8px", borderRadius: "3px" }} />
                        </div>
                        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px", color: TEAL }}>{(item.topsis_score * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>

                  {/* Per-criterion table */}
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                      <thead>
                        <tr>
                          <th style={{ textAlign: "left", padding: "6px 8px", borderBottom: `1px solid ${LINE}`, color: "#7A7A70", fontWeight: 500 }}>Criterion</th>
                          {compareResult.ranking.map((item) => (
                            <th key={item.analysis_id} style={{ textAlign: "center", padding: "6px 8px", borderBottom: `1px solid ${LINE}`, color: TEAL, fontWeight: 600 }}>
                              #{item.rank} {item.label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {compareResult.criteria.map((key) => {
                          const cLabel = CRITERIA.find((c) => c.key === key)?.label || key;
                          const vals = compareResult.per_criterion[key] || {};
                          const scores = Object.values(vals);
                          const maxScore = Math.max(...scores);
                          return (
                            <tr key={key} style={{ borderBottom: `1px solid ${LINE}` }}>
                              <td style={{ padding: "6px 8px", color: "#5B5B54" }}>{cLabel}</td>
                              {compareResult.ranking.map((item) => {
                                const score = vals[item.label] ?? "—";
                                const isTop = score === maxScore;
                                return (
                                  <td key={item.analysis_id} style={{ textAlign: "center", padding: "6px 8px", fontFamily: "'IBM Plex Mono', monospace", fontWeight: isTop ? 600 : 400, color: isTop ? TEAL : INK }}>
                                    {typeof score === "number" ? score.toFixed(0) : score}
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </main>

      <footer style={styles.footer}>
        Decision support, not decision-making. Every suggested score is grounded only in extracted
        evidence; every override is logged.
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fonts (unchanged from prototype)
// ---------------------------------------------------------------------------

const fontImports = `
  @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
`;

// ---------------------------------------------------------------------------
// Design tokens (unchanged from prototype)
// ---------------------------------------------------------------------------

const INK       = "#1E2328";
const PAPER     = "#FAF9F6";
const PAPER_DIM = "#F1EFE9";
const TEAL      = "#1F6F78";
const TEAL_DIM  = "#E4EFEE";
const AMBER     = "#9C6B12";
const AMBER_DIM = "#F5ECD9";
const LINE      = "#DEDAD1";

// ---------------------------------------------------------------------------
// Styles (all values copied verbatim from prototype; only dropZone is new)
// ---------------------------------------------------------------------------

const styles = {
  page: {
    fontFamily: "'IBM Plex Sans', sans-serif",
    background: PAPER,
    color: INK,
    minHeight: "100%",
    padding: "0",
  },
  header: {
    borderBottom: `1px solid ${LINE}`,
    padding: "28px 32px 24px",
  },
  headerInner: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
    flexWrap: "wrap",
    gap: "16px",
    maxWidth: "1100px",
    margin: "0 auto",
  },
  eyebrow: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: "11px",
    letterSpacing: "0.12em",
    color: TEAL,
    marginBottom: "8px",
  },
  title: {
    fontFamily: "'Source Serif 4', serif",
    fontWeight: 600,
    fontSize: "34px",
    margin: 0,
    letterSpacing: "-0.01em",
  },
  subtitle: {
    fontSize: "14px",
    color: "#5B5B54",
    marginTop: "6px",
    maxWidth: "480px",
  },
  scoreBadge: {
    border: `1px solid ${LINE}`,
    borderRadius: "6px",
    padding: "10px 18px",
    textAlign: "right",
    background: PAPER_DIM,
  },
  scoreBadgeLabel: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: "10px",
    letterSpacing: "0.08em",
    color: "#7A7A70",
  },
  scoreBadgeValue: {
    fontFamily: "'Source Serif 4', serif",
    fontSize: "28px",
    fontWeight: 600,
    color: TEAL,
  },
  scoreBadgeMax: {
    fontSize: "14px",
    color: "#9A9A8E",
  },
  main: {
    maxWidth: "1100px",
    margin: "0 auto",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.3fr)",
    gap: "28px",
    padding: "28px 32px",
  },
  panelLabel: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: "11px",
    letterSpacing: "0.1em",
    color: "#9A9A8E",
    marginBottom: "10px",
  },
  inputPanel:   { display: "flex", flexDirection: "column" },
  resultsPanel: { display: "flex", flexDirection: "column" },

  // Drop zone replaces the textarea from the prototype
  dropZone: {
    minHeight: "200px",
    padding: "36px 24px",
    border: `2px dashed ${LINE}`,
    borderRadius: "6px",
    background: "#fff",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    textAlign: "center",
    transition: "border-color 0.15s, background 0.15s",
    userSelect: "none",
  },
  dropZoneActive: {
    borderColor: TEAL,
    background: TEAL_DIM,
  },
  dropZoneIcon: {
    fontSize: "28px",
    color: TEAL,
    marginBottom: "10px",
  },
  dropZoneText: {
    fontSize: "14px",
    fontWeight: 500,
    color: INK,
    marginBottom: "6px",
  },
  dropZoneHint: {
    fontSize: "12px",
    color: "#8A8A7E",
  },

  inputRow: { display: "flex", gap: "10px", marginTop: "12px" },
  primaryButton: {
    background: TEAL,
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    padding: "10px 18px",
    fontSize: "13px",
    fontWeight: 500,
    cursor: "pointer",
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  ghostButton: {
    background: "transparent",
    color: INK,
    border: `1px solid ${LINE}`,
    borderRadius: "6px",
    padding: "10px 18px",
    fontSize: "13px",
    cursor: "pointer",
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  errorBox: {
    marginTop: "12px",
    padding: "10px 12px",
    background: "#FBEAEA",
    border: "1px solid #E8B4B4",
    borderRadius: "6px",
    fontSize: "13px",
    color: "#8A2C2C",
  },
  noteBox: {
    marginTop: "14px",
    fontSize: "12px",
    color: "#8A8A7E",
    lineHeight: 1.5,
    borderLeft: `2px solid ${LINE}`,
    paddingLeft: "10px",
  },
  emptyState: {
    fontSize: "13px",
    color: "#9A9A8E",
    padding: "24px",
    border: `1px dashed ${LINE}`,
    borderRadius: "6px",
    textAlign: "center",
  },
  criterionCard: {
    border: `1px solid ${LINE}`,
    borderRadius: "6px",
    marginBottom: "10px",
    background: "#fff",
    overflow: "hidden",
  },
  criterionHeaderRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 16px",
    cursor: "pointer",
  },
  criterionLabel: { fontWeight: 600, fontSize: "14.5px" },
  criterionHint:  { fontSize: "12px", color: "#8A8A7E", marginTop: "2px" },
  criterionScoreCluster: { display: "flex", alignItems: "center", gap: "10px" },
  confidenceTag: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: "10px",
    letterSpacing: "0.05em",
    color: "#7A7A70",
    border: `1px solid ${LINE}`,
    borderRadius: "4px",
    padding: "2px 6px",
    textTransform: "uppercase",
  },
  confidenceLow: { color: AMBER, borderColor: AMBER },
  scorePillAI: {
    fontFamily: "'Source Serif 4', serif",
    fontWeight: 600,
    fontSize: "16px",
    color: TEAL,
    background: TEAL_DIM,
    borderRadius: "50%",
    width: "32px",
    height: "32px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  scorePillOverridden: {
    fontFamily: "'Source Serif 4', serif",
    fontWeight: 600,
    fontSize: "16px",
    color: AMBER,
    background: AMBER_DIM,
    borderRadius: "50%",
    width: "32px",
    height: "32px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  criterionBody: {
    padding: "0 16px 16px",
    borderTop: `1px solid ${LINE}`,
  },
  evidenceText:  { fontSize: "13.5px", lineHeight: 1.55, marginTop: "12px" },
  citationStub: {
    display: "inline-block",
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: "10.5px",
    letterSpacing: "0.04em",
    color: TEAL,
    background: TEAL_DIM,
    padding: "3px 8px",
    borderRadius: "3px",
    marginBottom: "10px",
  },
  rationaleText: {
    fontSize: "12.5px",
    color: "#5B5B54",
    fontStyle: "italic",
    marginBottom: "14px",
  },
  sliderRow:  { display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" },
  sliderLabel: { fontSize: "12px", color: "#7A7A70", width: "80px", flexShrink: 0 },
  slider:     { flex: 1, accentColor: TEAL },
  sliderValue: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: "12px",
    width: "24px",
    textAlign: "right",
  },
  verificationFlag: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: "10px",
    letterSpacing: "0.04em",
    color: "#9C3A00",
    background: "#FEF0E7",
    border: "1px solid #F4C09A",
    borderRadius: "4px",
    padding: "2px 6px",
    cursor: "help",
  },
  verificationNote: {
    marginTop: "8px",
    fontSize: "11.5px",
    color: "#9C3A00",
    fontFamily: "'IBM Plex Mono', monospace",
    background: "#FEF0E7",
    border: "1px solid #F4C09A",
    borderRadius: "4px",
    padding: "6px 8px",
  },
  aiSuggestionNote: {
    marginTop: "8px",
    fontSize: "11.5px",
    color: TEAL,
    fontFamily: "'IBM Plex Mono', monospace",
  },
  overrideNote: {
    marginTop: "4px",
    fontSize: "11.5px",
    color: AMBER,
    fontFamily: "'IBM Plex Mono', monospace",
  },
  footerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: "8px",
    padding: "12px 4px",
  },
  weightTotal: { fontSize: "12px", color: "#8A8A7E" },
  exportButton: {
    background: INK,
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    padding: "9px 16px",
    fontSize: "12.5px",
    cursor: "pointer",
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  footer: {
    textAlign: "center",
    fontSize: "11.5px",
    color: "#9A9A8E",
    padding: "18px",
    borderTop: `1px solid ${LINE}`,
  },
};
