const BASE = (import.meta.env.VITE_API_BASE || "/api").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function flatten(value) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(flatten).filter(Boolean).join(" ");
  if (typeof value === "object") {
    return Object.entries(value)
      .map(([key, v]) => {
        const hide = key === "detail" || key === "non_field_errors";
        return `${hide ? "" : key + ": "}${flatten(v)}`;
      })
      .join(" ");
  }
  return String(value);
}

async function request(path, { org, method = "GET", body, signal } = {}) {
  const headers = { Accept: "application/json" };
  if (org) headers["X-Organization"] = org;

  let res;
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body, signal });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError("Could not reach the server. Check that the backend is running.", 0);
  }

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    const err = data && data.error;
    throw new ApiError(
      flatten(err ? err.message : data) || `Request failed (${res.status}).`,
      res.status,
      err && err.code
    );
  }
  return data;
}

export const getTransactions = (org, signal) => request("/transactions/", { org, signal });
export const getLineItems = (org, signal) => request("/line-items/", { org, signal });
export const approveMatch = (org, id) => request(`/matches/${id}/approve/`, { org, method: "POST" });
export const rejectMatch = (org, id) => request(`/matches/${id}/reject/`, { org, method: "POST" });
export const ignoreTransaction = (org, id) =>
  request(`/transactions/${id}/ignore/`, { org, method: "POST" });

export function importStatement(org, file) {
  const form = new FormData();
  form.append("file", file);
  return request("/imports/", { org, method: "POST", body: form });
}