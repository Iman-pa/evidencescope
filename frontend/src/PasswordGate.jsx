import { useEffect, useState } from "react";
import { verifyDemoAccess, storeDemoKey, checkHealth, AuthError } from "./api.js";
import { COLORS, RADIUS, FONT_STACK } from "./theme.js";

function EyeIcon(props) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon(props) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a21.8 21.8 0 0 1 5.06-6.06M9.9 4.24A10.4 10.4 0 0 1 12 4c7 0 11 8 11 8a21.77 21.77 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

export default function PasswordGate({ onUnlock }) {
  const [code, setCode] = useState("");
  const [status, setStatus] = useState("idle"); // idle | checking | error
  const [errorMsg, setErrorMsg] = useState("");
  const [waking, setWaking] = useState(false);
  const [showCode, setShowCode] = useState(false);

  useEffect(() => {
    // Proactively warm the server on load — gives a Render free-tier cold
    // start a head start before the user finishes typing the access code.
    checkHealth().catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!code.trim() || status === "checking") return;
    setStatus("checking");
    setErrorMsg("");
    const wakeTimer = setTimeout(() => setWaking(true), 3000);
    try {
      await verifyDemoAccess(code.trim());
      storeDemoKey(code.trim());
      onUnlock();
    } catch (err) {
      if (err instanceof AuthError) {
        setErrorMsg("That access code isn't right. Double-check and try again.");
      } else {
        setErrorMsg(err.message || "Couldn't reach the server. Please try again.");
      }
      setStatus("error");
    } finally {
      clearTimeout(wakeTimer);
      setWaking(false);
    }
  };

  return (
    <div style={styles.page}>
      <div className="es-card" style={styles.card}>
        <div style={styles.eyebrow}>EVIDENCESCOPE · LIVE DEMO</div>
        <h1 style={styles.title}>This demo is access-gated</h1>
        <p style={styles.subtitle}>
          EvidenceScope calls the Claude API on every analysis, so this demo is
          protected by an access code to keep usage in check. Enter the code
          you were given to continue.
        </p>

        {waking && (
          <div style={styles.wakingBanner}>
            Waking up the server — this can take up to 50 seconds on first load.
          </div>
        )}

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.inputWrapper}>
            <input
              className="es-input"
              style={styles.input}
              type={showCode ? "text" : "password"}
              placeholder="Access code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoFocus
              disabled={status === "checking"}
            />
            <button
              type="button"
              className="es-icon-btn"
              onClick={() => setShowCode((v) => !v)}
              style={styles.toggleVisibilityButton}
              aria-label={showCode ? "Hide access code" : "Show access code"}
              tabIndex={-1}
            >
              {showCode ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
          <button
            type="submit"
            className="es-btn es-btn-primary"
            style={styles.submitButton}
            disabled={status === "checking" || !code.trim()}
          >
            {status === "checking" ? (waking ? "Waking up…" : "Checking…") : "Enter"}
          </button>
        </form>

        {errorMsg && <div style={styles.errorBox}>{errorMsg}</div>}

        <p style={styles.footnote}>
          No patient data is used anywhere in this tool — only public HTA
          documents.
        </p>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "24px",
    background: COLORS.bg,
  },
  card: {
    width: "100%",
    maxWidth: "440px",
    padding: "36px",
  },
  eyebrow: {
    fontSize: "12px",
    fontWeight: 600,
    letterSpacing: "0.1em",
    color: COLORS.primary,
    marginBottom: "12px",
  },
  title: {
    fontFamily: FONT_STACK,
    fontWeight: 700,
    fontSize: "26px",
    lineHeight: 1.3,
    margin: "0 0 12px",
    color: COLORS.ink,
  },
  subtitle: {
    fontSize: "15px",
    lineHeight: 1.6,
    color: COLORS.inkMuted,
    margin: "0 0 24px",
  },
  wakingBanner: {
    background: COLORS.blueTint,
    color: COLORS.blue,
    border: `1px solid ${COLORS.blue}33`,
    borderRadius: RADIUS,
    padding: "12px 14px",
    fontSize: "14px",
    marginBottom: "20px",
  },
  form: { display: "flex", gap: "10px" },
  inputWrapper: { position: "relative", flex: 1 },
  input: { width: "100%", padding: "12px 44px 12px 14px", fontSize: "16px" },
  toggleVisibilityButton: {
    position: "absolute",
    top: "50%",
    right: "6px",
    transform: "translateY(-50%)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: "30px",
    height: "30px",
    padding: 0,
    background: "transparent",
    border: "none",
    borderRadius: "8px",
    color: COLORS.primary,
    cursor: "pointer",
  },
  submitButton: { padding: "12px 22px", fontSize: "15px", whiteSpace: "nowrap" },
  errorBox: {
    marginTop: "16px",
    padding: "12px 14px",
    background: COLORS.terracottaTint,
    color: "#8A4A24",
    border: `1px solid ${COLORS.terracotta}55`,
    borderRadius: RADIUS,
    fontSize: "14px",
  },
  footnote: {
    marginTop: "28px",
    fontSize: "12.5px",
    lineHeight: 1.6,
    color: COLORS.inkFaint,
  },
};
