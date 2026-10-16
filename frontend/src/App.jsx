import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api.js";

const ORGS = [
  { slug: "northwind", name: "Northwind Ventures" },
  { slug: "bluebird", name: "Bluebird Capital" },
];

const STATUS = {
  suggested: "Suggested",
  needs_review: "Needs review",
  reconciled: "Reconciled",
  ignored: "Ignored",
};

const ITEM_STATUS = {
  open: "Open",
  partially_funded: "Partially funded",
  funded: "Funded",
};

const formatMoney = (value) => {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return (
    "₹" +
    n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  );
};

const formatDate = (value) => {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value || "—";
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
};

const describeIssue = (issue) =>
  typeof issue === "string"
    ? issue
    : Object.entries(issue || {})
        .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
        .join(", ");

function Logo({ size = 36 }) {
  return (
    <svg
      width={size}
      height={size * 1.12}
      viewBox="0 0 80 90"
      role="img"
      aria-label="RMBI"
      className="logo"
    >
      <path d="M40 2 76 13v31c0 22-15 38-36 44C19 82 4 66 4 44V13z" fill="#0B1F4B" />
      <path
        d="M40 8 70 17v27c0 18-12 31-30 37C22 75 10 62 10 44V17z"
        fill="none"
        stroke="#7FB2FF"
        strokeWidth="1.2"
        opacity=".8"
      />
      <path d="M22 62V28h17c7 0 11 4 11 10s-4 9-9 10l11 14h-8L35 49h-6v13zm7-19h9c3 0 5-2 5-5s-2-5-5-5h-9z" fill="#FFFFFF" />
      <rect x="52" y="28" width="6" height="34" fill="#38D200" />
    </svg>
  );
}

function Splash({ onDone }) {
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const fade = setTimeout(() => setLeaving(true), 2400);
    const done = setTimeout(onDone, 3000);
    return () => {
      clearTimeout(fade);
      clearTimeout(done);
    };
  }, [onDone]);

  return (
    <div
      className={`splash${leaving ? " is-leaving" : ""}`}
      role="button"
      tabIndex={0}
      aria-label="Continue to RMBI"
      onClick={onDone}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " " || e.key === "Escape") onDone();
      }}
    >
      <div className="splash-content">
        <div className="splash-logo">
          <Logo size={104} />
        </div>
        <h1>RMBI</h1>
        <p className="splash-name">Real Madrid Bank of India</p>
        <span className="splash-rule" aria-hidden="true" />
        <p className="splash-tag">Capital Call Reconciliation</p>
      </div>
      <span className="splash-hint">Click anywhere to continue</span>
    </div>
  );
}

function Badge({ status }) {
  return (
    <span className={`badge badge-${status}`}>
      <i aria-hidden="true" />
      {STATUS[status] || status}
    </span>
  );
}

function Importer({ busy, result, fileName, onFile }) {
  const [dragging, setDragging] = useState(false);
  const input = useRef(null);

  const take = (file) => {
    if (file) onFile(file);
  };

  return (
    <section className="panel" aria-labelledby="import-title">
      <header className="panel-head">
        <div>
          <h2 id="import-title">Import bank statement</h2>
          <p>Upload a CSV with date, description, amount, type and reference columns.</p>
        </div>
      </header>

      <div
        className={`dropzone${dragging ? " is-dragging" : ""}${busy ? " is-busy" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          take(e.dataTransfer.files[0]);
        }}
      >
        <div className="dropzone-icon" aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
          </svg>
        </div>
        <div className="dropzone-copy">
          <strong>{busy ? "Uploading statement…" : "Drop a CSV statement here"}</strong>
          <span>{fileName ? fileName : "CSV only, up to 5 MB"}</span>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy}
          onClick={() => input.current.click()}
        >
          Choose file
        </button>
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => {
            take(e.target.files[0]);
            e.target.value = "";
          }}
        />
      </div>

      {result && (
        <div className="import-result" role="status">
          <dl className="import-counts">
            <div>
              <dt>Imported</dt>
              <dd>{result.imported_count}</dd>
            </div>
            <div>
              <dt>Duplicates skipped</dt>
              <dd>{result.duplicate_count}</dd>
            </div>
            <div>
              <dt>Invalid rows</dt>
              <dd className={result.error_count ? "is-negative" : ""}>{result.error_count}</dd>
            </div>
          </dl>

          {result.errors?.length > 0 && (
            <details className="issue-block" open>
              <summary>Rows with errors ({result.errors.length})</summary>
              <ul className="issue-list is-error">
                {result.errors.map((item, i) => (
                  <li key={i}>{describeIssue(item)}</li>
                ))}
              </ul>
            </details>
          )}

          {result.duplicates?.length > 0 && (
            <details className="issue-block">
              <summary>Skipped duplicates ({result.duplicates.length})</summary>
              <ul className="issue-list">
                {result.duplicates.map((item, i) => (
                  <li key={i}>{describeIssue(item)}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
}

function TransactionTable({ txns, busyId, sortDir, onSort, onApprove, onReject, onIgnore, emptyText }) {
  if (!txns.length) {
    return <p className="empty">{emptyText}</p>;
  }

  return (
    <div className="table-wrap">
      <table className="txns">
        <thead>
          <tr>
            <th aria-sort={sortDir === "asc" ? "ascending" : "descending"}>
              <button type="button" className="sort" onClick={onSort}>
                Date <span aria-hidden="true">{sortDir === "asc" ? "↑" : "↓"}</span>
              </button>
            </th>
            <th>Bank description</th>
            <th className="num">Amount</th>
            <th>Status</th>
            <th>Suggested match</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {txns.map((t) => {
            const working = busyId === t.id;
            const proposed = t.matches.filter((m) => m.status === "proposed");
            const canIgnore = t.status === "suggested" || t.status === "needs_review";

            return (
              <tr key={t.id} className={working ? "is-working" : ""}>
                <td data-label="Date" className="nowrap">{formatDate(t.date)}</td>
                <td data-label="Description">
                  <div className="cell-title">{t.description}</div>
                  <div className="cell-sub">Ref {t.reference || "—"}</div>
                </td>
                <td data-label="Amount" className={`num ${t.type}`}>{formatMoney(t.amount)}</td>
                <td data-label="Status"><Badge status={t.status} /></td>
                <td data-label="Match">
                  {t.matches.length === 0 && (
                    <span className="cell-sub">{t.review_reason || "No match proposed."}</span>
                  )}
                  {t.matches.map((m) => (
                    <div key={m.id} className="match">
                      <div className="match-head">
                        <strong>{m.investor_name}</strong>
                        <code>{m.line_item_reference}</code>
                        <span className="cell-sub">{formatMoney(m.amount)}</span>
                        {m.status !== "proposed" && (
                          <span className={`match-state is-${m.status}`}>{m.status}</span>
                        )}
                      </div>
                      {m.reason && <div className="cell-sub">{m.reason}</div>}
                    </div>
                  ))}
                  {t.review_reason && t.matches.length > 0 && (
                    <div className="review-note">{t.review_reason}</div>
                  )}
                </td>
                <td data-label="Actions" className="actions">
                  {proposed.map((m) => (
                    <div key={m.id} className="action-pair">
                      <button
                        type="button"
                        className="btn btn-success"
                        disabled={working}
                        onClick={() => onApprove(t.id, m.id)}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="btn btn-outline"
                        disabled={working}
                        onClick={() => onReject(t.id, m.id)}
                      >
                        Reject
                      </button>
                    </div>
                  ))}
                  {canIgnore && (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={working}
                      onClick={() => onIgnore(t.id)}
                    >
                      Ignore
                    </button>
                  )}
                  {working && <span className="cell-sub">Updating…</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function LineItems({ items }) {
  if (!items.length) {
    return <p className="empty">No capital-call records for this organization.</p>;
  }

  return (
    <ul className="items">
      {items.map((i) => {
        const called = Number(i.called_amount);
        const pct = called > 0 ? Math.min(100, Math.max(0, (Number(i.funded_amount) / called) * 100)) : 0;

        return (
          <li key={i.id}>
            <div className="item-head">
              <div>
                <div className="cell-title">{i.investor_name}</div>
                <code>{i.reference}</code>
              </div>
              <span className={`item-status is-${i.status}`}>{ITEM_STATUS[i.status] || i.status}</span>
            </div>
            <div
              className="bar"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={Math.round(pct)}
              aria-label={`${i.investor_name} funded`}
            >
              <span style={{ width: `${pct}%` }} />
            </div>
            <dl className="item-figures">
              <div><dt>Called</dt><dd>{formatMoney(i.called_amount)}</dd></div>
              <div><dt>Funded</dt><dd>{formatMoney(i.funded_amount)}</dd></div>
              <div><dt>Remaining</dt><dd>{formatMoney(i.remaining_amount)}</dd></div>
            </dl>
          </li>
        );
      })}
    </ul>
  );
}

export default function App() {
  const [splash, setSplash] = useState(true);
  const dismissSplash = useCallback(() => setSplash(false), []);
  const [org, setOrg] = useState(ORGS[0].slug);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [sortDir, setSortDir] = useState("desc");
  const [busyId, setBusyId] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [fileName, setFileName] = useState("");
  const [notice, setNotice] = useState(null);
  const controller = useRef(null);
  const orgRef = useRef(org);
  orgRef.current = org;

  const load = useCallback(async (slug, { silent = false } = {}) => {
    controller.current?.abort();
    const c = new AbortController();
    controller.current = c;
    if (!silent) {
      setData(null);
      setLoading(true);
    }
    setError("");
    try {
      const [txns, items] = await Promise.all([
        api.getTransactions(slug, c.signal),
        api.getLineItems(slug, c.signal),
      ]);
      setData({ org: slug, txns, items });
    } catch (e) {
      if (e.name === "AbortError") return;
      setError(e.message);
    } finally {
      if (controller.current === c) setLoading(false);
    }
  }, []);

  useEffect(() => {
    setImportResult(null);
    setFileName("");
    setNotice(null);
    setFilter("all");
    setQuery("");
    load(org);
    return () => controller.current?.abort();
  }, [org, load]);

  useEffect(() => {
    if (!notice || notice.kind !== "ok") return undefined;
    const timer = setTimeout(() => setNotice(null), 4500);
    return () => clearTimeout(timer);
  }, [notice]);

  const runAction = async (txnId, action, successText) => {
    const slug = org;
    setBusyId(txnId);
    setNotice(null);
    try {
      await action();
      if (orgRef.current !== slug) return;
      setNotice({ kind: "ok", text: successText });
      await load(slug, { silent: true });
    } catch (e) {
      if (orgRef.current === slug) setNotice({ kind: "err", text: e.message });
    } finally {
      setBusyId(null);
    }
  };

  const upload = async (file) => {
    const slug = org;
    setNotice(null);
    setImportResult(null);
    if (!/\.csv$/i.test(file.name)) {
      setNotice({ kind: "err", text: "The selected file is not a CSV. Choose a .csv statement." });
      return;
    }
    setFileName(file.name);
    setUploading(true);
    try {
      const res = await api.importStatement(slug, file);
      if (orgRef.current !== slug) return;
      setImportResult(res);
      setNotice({ kind: "ok", text: `Statement processed: ${res.imported_count} transaction(s) imported.` });
      await load(slug, { silent: true });
    } catch (e) {
      if (orgRef.current === slug) setNotice({ kind: "err", text: e.message });
    } finally {
      setUploading(false);
    }
  };

  const fresh = data && data.org === org ? data : null;
  const txns = fresh ? fresh.txns : [];
  const items = fresh ? fresh.items : [];

  const countBy = (status) => txns.filter((t) => t.status === status).length;

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = txns.filter((t) => {
      if (filter !== "all" && t.status !== filter) return false;
      if (!q) return true;
      const haystack = [
        t.description,
        t.reference,
        ...t.matches.flatMap((m) => [m.investor_name, m.line_item_reference]),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
    return list.sort((a, b) =>
      sortDir === "asc" ? String(a.date).localeCompare(b.date) : String(b.date).localeCompare(a.date)
    );
  }, [txns, filter, query, sortDir]);

  const orgName = ORGS.find((o) => o.slug === org).name;
  const pending = countBy("needs_review") + countBy("suggested");
  const openItems = items.filter((i) => i.status !== "funded").length;
  const outstanding = items.reduce((sum, i) => sum + (Number(i.remaining_amount) || 0), 0);

  const nav = [
    ["all", "All transactions", txns.length],
    ...Object.entries(STATUS).map(([key, label]) => [key, label, countBy(key)]),
  ];

  const emptyText = !txns.length
    ? "No transactions yet. Import a bank statement to begin."
    : "No transactions match the current filter.";

  return (
    <>
      {splash && <Splash onDone={dismissSplash} />}

      <header className="topbar">
        <div className="brand">
          <Logo size={34} />
          <div className="brand-text">
            <strong>RMBI</strong>
            <span>Real Madrid Bank of India</span>
          </div>
        </div>
        <div className="topbar-title">Capital Call Reconciliation</div>
        <label className="org-select">
          <span>Organization</span>
          <select value={org} onChange={(e) => setOrg(e.target.value)}>
            {ORGS.map((o) => (
              <option key={o.slug} value={o.slug}>{o.name}</option>
            ))}
          </select>
        </label>
      </header>

      <div className="shell">
        <nav className="sidebar" aria-label="Transaction status">
          <span className="sidebar-label">Transactions</span>
          {nav.map(([key, label, n]) => (
            <button
              key={key}
              type="button"
              className={filter === key ? "is-active" : ""}
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
            >
              <span>{label}</span>
              <em>{fresh ? n : "–"}</em>
            </button>
          ))}
        </nav>

        <main>
          <div className="page-head">
            <div>
              <p className="eyebrow">Reconciliation overview</p>
              <h1>{orgName}</h1>
            </div>
          </div>

          <div className="kpis">
            <div className="kpi">
              <span>Bank transactions</span>
              <strong>{fresh ? txns.length : "–"}</strong>
            </div>
            <div className="kpi">
              <span>Pending review</span>
              <strong>{fresh ? pending : "–"}</strong>
            </div>
            <div className="kpi">
              <span>Reconciled</span>
              <strong>{fresh ? countBy("reconciled") : "–"}</strong>
            </div>
            <div className="kpi">
              <span>Open capital calls</span>
              <strong>{fresh ? openItems : "–"}</strong>
              {fresh && <small>{formatMoney(outstanding)} outstanding</small>}
            </div>
          </div>

          <div className="alerts" aria-live="polite">
            {notice && (
              <div className={`alert alert-${notice.kind}`} role={notice.kind === "err" ? "alert" : "status"}>
                <span>{notice.text}</span>
                <button type="button" aria-label="Dismiss" onClick={() => setNotice(null)}>×</button>
              </div>
            )}
            {error && (
              <div className="alert alert-err" role="alert">
                <span>{error}</span>
                <button type="button" className="btn btn-outline" onClick={() => load(org)}>Retry</button>
              </div>
            )}
          </div>

          <Importer busy={uploading} result={importResult} fileName={fileName} onFile={upload} />

          <div className="layout">
            <section className="panel" aria-labelledby="txn-title" aria-busy={loading}>
              <header className="panel-head">
                <div>
                  <h2 id="txn-title">Transaction review</h2>
                  <p>
                    {fresh ? `${visible.length} of ${txns.length} transactions` : "Loading transactions"}
                  </p>
                </div>
                <input
                  type="search"
                  className="search"
                  placeholder="Search description, reference or investor"
                  aria-label="Search transactions"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </header>

              {loading && !fresh ? (
                <p className="empty"><span className="spinner" /> Loading {orgName} transactions…</p>
              ) : fresh ? (
                <TransactionTable
                  txns={visible}
                  busyId={busyId}
                  sortDir={sortDir}
                  onSort={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
                  emptyText={emptyText}
                  onApprove={(tid, mid) => runAction(tid, () => api.approveMatch(org, mid), "Match approved and reconciled.")}
                  onReject={(tid, mid) => runAction(tid, () => api.rejectMatch(org, mid), "Match rejected.")}
                  onIgnore={(tid) => runAction(tid, () => api.ignoreTransaction(org, tid), "Transaction excluded from reconciliation.")}
                />
              ) : null}
            </section>

            <aside className="panel" aria-labelledby="calls-title" aria-busy={loading}>
              <header className="panel-head">
                <div>
                  <h2 id="calls-title">Capital-call records</h2>
                  <p>{fresh ? `${items.length} records` : "Loading records"}</p>
                </div>
              </header>
              {loading && !fresh ? (
                <p className="empty"><span className="spinner" /> Loading…</p>
              ) : (
                fresh && <LineItems items={items} />
              )}
            </aside>
          </div>
        </main>
      </div>
    </>
  );
}
