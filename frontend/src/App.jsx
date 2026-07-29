import { useState, useCallback, useRef, useEffect } from "react";
import {
  callAnalyze,
  callOverride,
  callCompare,
  getStoredDemoKey,
  clearStoredDemoKey,
  verifyDemoAccess,
  AuthError,
  RateLimitError,
} from "./api.js";
import PasswordGate from "./PasswordGate.jsx";
import { COLORS, RADIUS, FONT_STACK, globalStyleSheet } from "./theme.js";

// ---------------------------------------------------------------------------
// EvidenceScope — evidence-linked MCDA for health technology review
// Styled to match the personal-portfolio design system: warm sage/amber
// palette, Inter type, 14px radius cards. Teal→primary (AI-suggested) and
// amber (human-overridden) semantics from the original design are preserved.
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
function toDisplayScore(backendVal) {
  return (backendVal * 8 + 1).toFixed(2);
}

// ---------------------------------------------------------------------------
// Top-level shell: gates the app behind an access code, restores an existing
// session from sessionStorage, and drops back to the gate if the stored code
// turns out to be invalid or expired.
// ---------------------------------------------------------------------------

export default function App() {
  const [unlocked, setUnlocked] = useState(() => Boolean(getStoredDemoKey()));

  useEffect(() => {
    const storedKey = getStoredDemoKey();
    if (!storedKey) return;
    let cancelled = false;
    verifyDemoAccess(storedKey).catch(() => {
      if (!cancelled) {
        clearStoredDemoKey();
        setUnlocked(false);
      }
    });
    return () => { cancelled = true; };
  }, []);

  const handleAuthError = useCallback(() => {
    clearStoredDemoKey();
    setUnlocked(false);
  }, []);

  return (
    <>
      <style>{globalStyleSheet}</style>
      {unlocked ? (
        <EvidenceScope onAuthError={handleAuthError} />
      ) : (
        <PasswordGate onUnlock={() => setUnlocked(true)} />
      )}
    </>
  );
}

function EvidenceScope({ onAuthError }) {
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
  const [rateLimitMsg, setRateLimitMsg]     = useState("");
  const [analysisLabel, setAnalysisLabel]   = useState("");

  // Saved analyses for cross-drug comparison
  const [savedAnalyses, setSavedAnalyses]   = useState([]); // [{id, label, scores, weights}]
  const [compareResult, setCompareResult]   = useState(null);
  const [showCompare, setShowCompare]       = useState(false);
  const [compareError, setCompareError]     = useState("");

  // -------------------------------------------------------------------------
  // Shared handler for auth/rate-limit errors that any API call can surface
  // -------------------------------------------------------------------------

  const handleApiError = (err, fallbackSetter) => {
    if (err instanceof AuthError) {
      onAuthError();
      return;
    }
    if (err instanceof RateLimitError) {
      setRateLimitMsg(err.message);
      return;
    }
    fallbackSetter(err.message || "Something went wrong. Please try again.");
  };

  // -------------------------------------------------------------------------
  // File selection
  // -------------------------------------------------------------------------

  const applyFiles = (files) => {
    const pdfs = Array.from(files).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdfs.length === 0) {
      setErrorMsg("Please select PDF files — other file types aren't supported.");
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
    setRateLimitMsg("");
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
      if (err instanceof AuthError) {
        onAuthError();
        return;
      }
      if (err instanceof RateLimitError) {
        setRateLimitMsg(err.message);
        setPhase("error");
        return;
      }
      setErrorMsg(err.message || "Something went wrong analysing this report.");
      setPhase("error");
    }
  }, [selectedFiles, onAuthError]);

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
      handleApiError(err, (msg) => setErrorMsg(`Override failed: ${msg}`));
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
      handleApiError(err, (msg) => setErrorMsg(`Override failed: ${msg}`));
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
      handleApiError(err, (msg) => setCompareError(`Comparison failed: ${msg}`));
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
      <header style={styles.header}>
        <div className="es-header-inner">
          <div>
            <div style={styles.eyebrow}>EVIDENCE-LINKED MCDA · HEALTH TECHNOLOGY REVIEW</div>
            <h1 style={styles.title}>EvidenceScope</h1>
            <p style={styles.subtitle}>
              Every score traces back to evidence, or to a documented human decision. Nothing in between.
            </p>
          </div>
          <div className="es-card" style={styles.scoreBadge}>
            <div style={styles.scoreBadgeLabel}>Weighted Score</div>
            <div style={styles.scoreBadgeValue}>
              {weightedScore !== null ? toDisplayScore(weightedScore) : "—"}
              <span style={styles.scoreBadgeMax}> / 9</span>
            </div>
          </div>
        </div>
      </header>

      <main className="es-main">
        {/* ---------------------------------------------------------------- */}
        {/* 01 — SOURCE DOCUMENT                                             */}
        {/* ---------------------------------------------------------------- */}
        <section style={styles.inputPanel}>
          <div style={styles.panelLabel}>01 — SOURCE DOCUMENT</div>

          {/* Drop zone */}
          <div
            className="es-card"
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
              className="es-btn es-btn-primary"
              style={styles.primaryButton}
              onClick={handleAnalyze}
              disabled={phase === "uploading"}
            >
              {phase === "uploading" ? "Extracting evidence…" : "Analyze report"}
            </button>
            <button
              className="es-btn es-btn-ghost"
              style={styles.ghostButton}
              onClick={() => { setSelectedFiles([]); if (fileInputRef.current) fileInputRef.current.value = ""; }}
              disabled={phase === "uploading"}
            >
              Clear
            </button>
          </div>

          {rateLimitMsg && (
            <div style={styles.rateLimitBox}>{rateLimitMsg}</div>
          )}

          {(phase === "error" || errorMsg) && !rateLimitMsg && (
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
              <div style={{ marginBottom: "8px", fontSize: "14px", color: COLORS.primary, fontWeight: 600 }}>
                Reading document and extracting evidence…
              </div>
              <div style={{ fontSize: "12.5px", color: COLORS.inkFaint, lineHeight: 1.6 }}>
                This typically takes 60–90 seconds while the model reads each page and scores
                all six criteria. It can take longer on the very first request if the server
                had been asleep.
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
                <div key={c.key} className="es-card" style={styles.criterionCard}>
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
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                <button
                  className="es-btn es-btn-ghost"
                  style={{
                    ...styles.ghostButton,
                    fontSize: "13px",
                    padding: "8px 14px",
                  }}
                  onClick={handleSaveForComparison}
                  disabled={savedAnalyses.some((a) => a.id === analysisId)}
                  title="Save this analysis to compare against others"
                >
                  {savedAnalyses.some((a) => a.id === analysisId) ? "Saved" : "Save for comparison"}
                </button>
                <button className="es-btn es-btn-dark" style={styles.exportButton} onClick={exportReport}>
                  Export scorecard (.md)
                </button>
              </div>
            </div>
          )}

          {/* Cross-drug comparison panel */}
          {savedAnalyses.length >= 2 && (
            <div style={{ marginTop: "20px", borderTop: `1px solid ${COLORS.cardBorder}`, paddingTop: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
                <div style={{ fontSize: "12px", fontWeight: 600, letterSpacing: "0.06em", color: COLORS.inkFaint }}>
                  03 — CROSS-DRUG COMPARISON ({savedAnalyses.length} saved)
                </div>
                <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                  {savedAnalyses.map((a) => (
                    <span key={a.id} style={{ fontSize: "12px", fontWeight: 500, color: COLORS.primary, background: COLORS.primaryTint, padding: "3px 10px", borderRadius: "999px" }}>
                      {a.label}
                    </span>
                  ))}
                  <button className="es-btn es-btn-primary" style={{ fontSize: "13px", padding: "8px 16px" }} onClick={handleCompare}>
                    Run comparison
                  </button>
                  <button className="es-btn es-btn-ghost" style={{ fontSize: "13px", padding: "8px 12px" }} onClick={() => { setSavedAnalyses([]); setCompareResult(null); setShowCompare(false); }}>
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
                      <div key={item.analysis_id} style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                        <span style={{ fontSize: "12px", fontWeight: 600, color: COLORS.inkFaint, width: "22px" }}>#{item.rank}</span>
                        <span style={{ fontWeight: 600, fontSize: "14px", minWidth: "120px" }}>{item.label}</span>
                        <div style={{ flex: 1, background: COLORS.primaryTint, borderRadius: "999px", height: "8px" }}>
                          <div style={{ width: `${(item.topsis_score * 100).toFixed(1)}%`, background: COLORS.primary, height: "8px", borderRadius: "999px" }} />
                        </div>
                        <span style={{ fontSize: "12px", fontWeight: 600, color: COLORS.primary, width: "48px", textAlign: "right" }}>{(item.topsis_score * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>

                  {/* Per-criterion table */}
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                      <thead>
                        <tr>
                          <th style={{ textAlign: "left", padding: "8px", borderBottom: `1px solid ${COLORS.cardBorder}`, color: COLORS.inkMuted, fontWeight: 500 }}>Criterion</th>
                          {compareResult.ranking.map((item) => (
                            <th key={item.analysis_id} style={{ textAlign: "center", padding: "8px", borderBottom: `1px solid ${COLORS.cardBorder}`, color: COLORS.primary, fontWeight: 600 }}>
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
                            <tr key={key} style={{ borderBottom: `1px solid ${COLORS.cardBorder}` }}>
                              <td style={{ padding: "8px", color: COLORS.inkMuted }}>{cLabel}</td>
                              {compareResult.ranking.map((item) => {
                                const score = vals[item.label] ?? "—";
                                const isTop = score === maxScore;
                                return (
                                  <td key={item.analysis_id} style={{ textAlign: "center", padding: "8px", fontWeight: isTop ? 700 : 400, color: isTop ? COLORS.primary : COLORS.ink }}>
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
// Styles — portfolio design system (see theme.js for shared tokens)
// ---------------------------------------------------------------------------

const styles = {
  page: {
    fontFamily: FONT_STACK,
    background: COLORS.bg,
    color: COLORS.ink,
    minHeight: "100%",
  },
  header: {
    padding: "32px 32px 28px",
  },
  eyebrow: {
    fontSize: "12px",
    fontWeight: 600,
    letterSpacing: "0.1em",
    color: COLORS.primary,
    marginBottom: "10px",
  },
  title: {
    fontFamily: FONT_STACK,
    fontWeight: 700,
    fontSize: "34px",
    margin: 0,
    letterSpacing: "-0.01em",
  },
  subtitle: {
    fontSize: "15px",
    lineHeight: 1.6,
    color: COLORS.inkMuted,
    marginTop: "8px",
    maxWidth: "480px",
  },
  scoreBadge: {
    padding: "14px 22px",
    textAlign: "right",
  },
  scoreBadgeLabel: {
    fontSize: "11px",
    fontWeight: 600,
    letterSpacing: "0.08em",
    color: COLORS.inkFaint,
  },
  scoreBadgeValue: {
    fontFamily: FONT_STACK,
    fontSize: "30px",
    fontWeight: 700,
    color: COLORS.primary,
  },
  scoreBadgeMax: {
    fontSize: "15px",
    fontWeight: 500,
    color: COLORS.inkFaint,
  },
  panelLabel: {
    fontSize: "12px",
    fontWeight: 600,
    letterSpacing: "0.08em",
    color: COLORS.inkFaint,
    marginBottom: "12px",
  },
  inputPanel:   { display: "flex", flexDirection: "column" },
  resultsPanel: { display: "flex", flexDirection: "column" },

  dropZone: {
    minHeight: "200px",
    padding: "36px 24px",
    borderStyle: "dashed",
    borderWidth: "2px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    textAlign: "center",
    userSelect: "none",
  },
  dropZoneActive: {
    borderColor: COLORS.primary,
    background: COLORS.primaryTint,
  },
  dropZoneIcon: {
    fontSize: "28px",
    color: COLORS.primary,
    marginBottom: "10px",
  },
  dropZoneText: {
    fontSize: "15px",
    fontWeight: 600,
    color: COLORS.ink,
    marginBottom: "6px",
  },
  dropZoneHint: {
    fontSize: "13px",
    color: COLORS.inkFaint,
  },

  inputRow: { display: "flex", gap: "10px", marginTop: "14px" },
  primaryButton: { padding: "12px 20px", fontSize: "14px" },
  ghostButton:   { padding: "12px 20px", fontSize: "14px" },
  errorBox: {
    marginTop: "14px",
    padding: "12px 14px",
    background: COLORS.terracottaTint,
    border: `1px solid ${COLORS.terracotta}55`,
    borderRadius: RADIUS,
    fontSize: "14px",
    color: "#8A4A24",
  },
  rateLimitBox: {
    marginTop: "14px",
    padding: "12px 14px",
    background: COLORS.blueTint,
    border: `1px solid ${COLORS.blue}55`,
    borderRadius: RADIUS,
    fontSize: "14px",
    color: COLORS.blue,
  },
  noteBox: {
    marginTop: "16px",
    fontSize: "13px",
    color: COLORS.inkFaint,
    lineHeight: 1.6,
    borderLeft: `2px solid ${COLORS.cardBorder}`,
    paddingLeft: "12px",
  },
  emptyState: {
    fontSize: "14px",
    color: COLORS.inkFaint,
    padding: "28px 24px",
    border: `1px dashed ${COLORS.cardBorder}`,
    borderRadius: RADIUS,
    textAlign: "center",
  },
  criterionCard: {
    marginBottom: "12px",
    overflow: "hidden",
  },
  criterionHeaderRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "16px 18px",
    cursor: "pointer",
    gap: "12px",
    flexWrap: "wrap",
  },
  criterionLabel: { fontWeight: 600, fontSize: "15.5px" },
  criterionHint:  { fontSize: "13px", color: COLORS.inkFaint, marginTop: "3px" },
  criterionScoreCluster: { display: "flex", alignItems: "center", gap: "10px" },
  confidenceTag: {
    fontSize: "11px",
    fontWeight: 600,
    letterSpacing: "0.03em",
    color: COLORS.inkMuted,
    border: `1px solid ${COLORS.cardBorder}`,
    borderRadius: "6px",
    padding: "3px 7px",
    textTransform: "uppercase",
  },
  confidenceLow: { color: COLORS.terracotta, borderColor: COLORS.terracotta },
  scorePillAI: {
    fontFamily: FONT_STACK,
    fontWeight: 700,
    fontSize: "16px",
    color: COLORS.primary,
    background: COLORS.primaryTint,
    borderRadius: "50%",
    width: "34px",
    height: "34px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  scorePillOverridden: {
    fontFamily: FONT_STACK,
    fontWeight: 700,
    fontSize: "16px",
    color: "#8A6A1E",
    background: COLORS.amberTint,
    borderRadius: "50%",
    width: "34px",
    height: "34px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  criterionBody: {
    padding: "0 18px 18px",
    borderTop: `1px solid ${COLORS.cardBorder}`,
  },
  evidenceText:  { fontSize: "14.5px", lineHeight: 1.65, marginTop: "14px" },
  citationStub: {
    display: "inline-block",
    fontSize: "12px",
    fontWeight: 600,
    letterSpacing: "0.02em",
    color: COLORS.primary,
    background: COLORS.primaryTint,
    padding: "4px 10px",
    borderRadius: "6px",
    marginBottom: "12px",
  },
  rationaleText: {
    fontSize: "13.5px",
    color: COLORS.inkMuted,
    fontStyle: "italic",
    marginBottom: "16px",
    lineHeight: 1.6,
  },
  sliderRow:  { display: "flex", alignItems: "center", gap: "12px", marginBottom: "10px" },
  sliderLabel: { fontSize: "13px", color: COLORS.inkMuted, width: "84px", flexShrink: 0 },
  slider:     { flex: 1 },
  sliderValue: {
    fontSize: "13px",
    fontWeight: 600,
    width: "30px",
    textAlign: "right",
  },
  verificationFlag: {
    fontSize: "11px",
    fontWeight: 600,
    letterSpacing: "0.02em",
    color: "#9C4A1A",
    background: COLORS.terracottaTint,
    border: `1px solid ${COLORS.terracotta}55`,
    borderRadius: "6px",
    padding: "3px 8px",
    cursor: "help",
  },
  verificationNote: {
    marginTop: "10px",
    fontSize: "12.5px",
    color: "#9C4A1A",
    background: COLORS.terracottaTint,
    border: `1px solid ${COLORS.terracotta}55`,
    borderRadius: "8px",
    padding: "8px 10px",
    lineHeight: 1.5,
  },
  aiSuggestionNote: {
    marginTop: "10px",
    fontSize: "12.5px",
    fontWeight: 500,
    color: COLORS.primary,
  },
  overrideNote: {
    marginTop: "6px",
    fontSize: "12.5px",
    fontWeight: 500,
    color: "#8A6A1E",
  },
  footerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: "10px",
    padding: "12px 4px",
    flexWrap: "wrap",
    gap: "10px",
  },
  weightTotal: { fontSize: "13px", color: COLORS.inkFaint },
  exportButton: {
    padding: "10px 18px",
    fontSize: "13.5px",
  },
  footer: {
    textAlign: "center",
    fontSize: "12.5px",
    color: COLORS.inkFaint,
    padding: "24px",
    borderTop: `1px solid ${COLORS.cardBorder}`,
    lineHeight: 1.6,
  },
};
