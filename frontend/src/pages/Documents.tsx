import { useState } from "react";
import { FileText, RefreshCw, Trash2 } from "lucide-react";
import DocumentDetailPanel from "../components/DocumentDetailPanel";
import StatusBadge from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import SearchTester from "../components/SearchTester";
import UploadDropzone from "../components/UploadDropzone";
import { useDocuments } from "../hooks/useDocuments";
import { deleteDocument, errorMessage, reprocessDocument } from "../services/documents";

export default function Documents() {
  const { documents, loading, error, refresh } = useDocuments();
  const [selected, setSelected] = useState<string | null>(null);
  const toast = useToast();

  async function remove(id: string, title: string) {
    if (!window.confirm(`Delete "${title}"? Its extracted data will be removed too.`)) return;
    try {
      await deleteDocument(id);
      if (selected === id) setSelected(null);
      toast("success", `${title} deleted.`);
      refresh();
    } catch (e) {
      toast("error", errorMessage(e));
    }
  }

  async function retry(id: string) {
    try { await reprocessDocument(id); refresh(); } catch (e) { toast("error", errorMessage(e)); }
  }

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
      <p className="mt-1 text-muted">Upload reports once, then ask questions about them in AI Analyst.</p>

      <div className="mt-6"><UploadDropzone onUploaded={refresh} /></div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-label="Uploaded documents">
          {error && (
            <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-loss">
              Couldn't load your documents. The list will retry automatically.
            </p>
          )}
          {loading ? (
            <div className="space-y-2" aria-busy>
              {[0, 1, 2].map((i) => <div key={i} className="h-16 animate-pulse rounded-lg bg-surface" />)}
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-lg border border-line bg-surface px-6 py-12 text-center">
              <FileText className="mx-auto size-8 text-muted" aria-hidden />
              <p className="mt-3 font-medium">No reports yet</p>
              <p className="mt-1 text-sm text-muted">Upload a PDF above to get started.</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {documents.map((d) => (
                <li key={d.id}
                    className={`flex items-center gap-3 rounded-lg border bg-surface p-3 ${selected === d.id ? "border-brand" : "border-line"}`}>
                  <button onClick={() => setSelected(d.id)} className="min-w-0 flex-1 text-left">
                    <div className="truncate font-medium">{d.title ?? d.filename}</div>
                    <div className="mt-0.5 truncate text-xs text-muted">
                      {[d.company, d.fiscal_year, d.page_count ? `${d.page_count} pages` : null].filter(Boolean).join(", ") || "Details appear after processing"}
                    </div>
                    {d.status === "failed" && d.error && <div className="mt-1 text-xs text-loss">{d.error}</div>}
                  </button>
                  <StatusBadge status={d.status} />
                  {(d.status === "failed" || d.status === "ready") && (
                    <button onClick={() => retry(d.id)} title={d.status === "failed" ? "Retry processing" : "Re-process"} aria-label={`Re-process ${d.title}`} className="rounded p-1.5 text-muted hover:bg-paper hover:text-ink">
                      <RefreshCw className="size-4" />
                    </button>
                  )}
                  <button onClick={() => remove(d.id, d.title ?? d.filename)} aria-label={`Delete ${d.title ?? d.filename}`}
                          className="rounded p-1.5 text-muted hover:bg-paper hover:text-loss">
                    <Trash2 className="size-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        {selected && <DocumentDetailPanel id={selected} onClose={() => setSelected(null)} />}
      </div>

      <SearchTester readyCount={documents.filter((d) => d.status === "ready").length} />
    </div>
  );
}
