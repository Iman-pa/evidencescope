/**
 * API wrappers for the EvidenceScope FastAPI backend.
 *
 * Base URL comes from VITE_API_URL (set in Vercel for production, pointing at
 * the deployed Render backend). Falls back to relative URLs, which the Vite
 * dev proxy forwards to localhost:8001.
 */

// Trailing slash stripped so `${API_BASE}/health` can never become a
// double-slash URL if VITE_API_URL was set with one (e.g. ".../onrender.com/").
const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const DEMO_KEY_STORAGE = "evidencescope_demo_key";

export function getStoredDemoKey() {
  return sessionStorage.getItem(DEMO_KEY_STORAGE) || "";
}

export function storeDemoKey(key) {
  sessionStorage.setItem(DEMO_KEY_STORAGE, key);
}

export function clearStoredDemoKey() {
  sessionStorage.removeItem(DEMO_KEY_STORAGE);
}

function authHeaders() {
  const key = getStoredDemoKey();
  return key ? { "X-Demo-Key": key } : {};
}

/** Thrown for 401s so callers can distinguish "wrong/expired code" from other errors. */
export class AuthError extends Error {}

/** Thrown for 429s so callers can show the friendly rate-limit message distinctly. */
export class RateLimitError extends Error {}

async function handleErrorResponse(resp) {
  const body = await resp.json().catch(() => ({}));
  const message = body.detail || `Server error ${resp.status}`;
  if (resp.status === 401) throw new AuthError(message);
  if (resp.status === 429) throw new RateLimitError(message);
  throw new Error(message);
}

export async function checkHealth() {
  const resp = await fetch(`${API_BASE}/health`);
  if (!resp.ok) throw new Error(`Server error ${resp.status}`);
  return resp.json();
}

export async function verifyDemoAccess(key) {
  const resp = await fetch(`${API_BASE}/auth/verify`, {
    method: "POST",
    headers: key ? { "X-Demo-Key": key } : {},
  });
  if (!resp.ok) await handleErrorResponse(resp);
  return resp.json();
}

export async function callAnalyze(files) {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  const resp = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!resp.ok) await handleErrorResponse(resp);
  return resp.json();
}

export async function callCompare(comparisons) {
  // comparisons: [{analysis_id, label}, ...]
  const resp = await fetch(`${API_BASE}/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ comparisons }),
  });
  if (!resp.ok) await handleErrorResponse(resp);
  return resp.json();
}

export async function callOverride({ analysisId, criterionKey, field, newValue }) {
  const resp = await fetch(`${API_BASE}/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      analysis_id:   analysisId,
      criterion_key: criterionKey,
      field,
      new_value:     newValue,
    }),
  });
  if (!resp.ok) await handleErrorResponse(resp);
  return resp.json();
}
