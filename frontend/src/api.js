/**
 * API wrappers for the EvidenceScope FastAPI backend.
 * All calls use relative URLs — Vite proxies them to localhost:8000 in dev.
 */

export async function callAnalyze(files) {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  const resp = await fetch("/analyze", { method: "POST", body: form });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `Server error ${resp.status}`);
  }
  return resp.json();
}

export async function callOverride({ analysisId, criterionKey, field, newValue }) {
  const resp = await fetch("/override", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      analysis_id:   analysisId,
      criterion_key: criterionKey,
      field,
      new_value:     newValue,
    }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `Server error ${resp.status}`);
  }
  return resp.json();
}
