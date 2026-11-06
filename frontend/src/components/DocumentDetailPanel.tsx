import { useEffect, useState } from "react";
import { ExternalLink, X } from "lucide-react";
import { documentFileUrl, errorMessage, getDocument } from "../services/documents";
import type { DocumentDetail } from "../types";

const TABLE_LABELS: Record<string, string> = {
  income_statement: "Income statement", balance_sheet: "Balance sheet", cash_flow: "Cash flow statement",
  segment: "Segment performance", expenses: "Expenses",
};

export default function DocumentDetailPanel({ id, onClose }: { id: string; onClose: () => void }) {
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDoc(null); setError(null);
    getDocument(id).then(setDoc).catch((e) => setError(errorMessage(e)));
  }, [id]);

  const fields: [string, string | number | null | undefined][] = doc
    ? [["Company", doc.company], ["Fiscal year", doc.fiscal_year], ["Report type", doc.report_type],
       ["Pages", doc.page_count], ["Tables found", doc.tables.length], ["Text chunks", doc.chunk_count]]
    : [];

  return (
    <aside className="rounded-lg border border-line bg-surface p-5" aria-label="Document details">
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-semibold">{doc?.title ?? "Document details"}</h2>
        <button onClick={onClose} aria-label="Close details" className="text-muted hover:text-ink"><X className="size-4" /></button>
      </div>
      {error && <p className="mt-4 text-sm text-loss">{error}</p>}
      {!doc && !error && <div className="mt-4 space-y-2" aria-busy><div className="h-4 w-2/3 animate-pulse rounded bg-paper" /><div className="h-4 w-1/2 animate-pulse rounded bg-paper" /></div>}
      {doc && (
        <>
          {doc.error && <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-loss">{doc.error}</p>}
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            {fields.map(([k, v]) => (
              <div key={k}><dt className="text-muted">{k}</dt><dd>{v ?? "Not detected"}</dd></div>
            ))}
          </dl>
          <a href={documentFileUrl(doc.id)} target="_blank" rel="noreferrer"
             className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline">
            Open original PDF <ExternalLink className="size-3.5" aria-hidden />
          </a>
          <h3 className="mt-6 text-sm font-medium">Extracted tables</h3>
          {doc.tables.length === 0 ? (
            <p className="mt-2 text-sm text-muted">No tables were found in this document.</p>
          ) : (
            <ul className="mt-2 divide-y divide-line text-sm">
              {doc.tables.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-3 py-2">
                  <span>{(t.table_type && TABLE_LABELS[t.table_type]) || t.title || "Table"}</span>
                  <a href={documentFileUrl(doc.id, t.page_number)} target="_blank" rel="noreferrer" className="shrink-0 text-brand hover:underline">
                    Page {t.page_number}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </aside>
  );
}
