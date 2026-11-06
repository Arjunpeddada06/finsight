import { useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { documentFileUrl, errorMessage } from "../services/documents";
import { searchDocuments } from "../services/search";
import type { SearchHit } from "../types";

export default function SearchTester({ readyCount }: { readyCount: number }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: FormEvent) {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setLoading(true); setError(null);
    try {
      setHits((await searchDocuments(query.trim())).hits);
    } catch (err) {
      setHits(null); setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mt-10" aria-label="Search your documents">
      <h2 className="text-lg font-semibold tracking-tight">Search your documents</h2>
      <p className="mt-1 text-sm text-muted">
        Finds the passages most relevant to a question, with their page numbers. This is the retrieval step the AI Analyst will build on.
      </p>
      <form onSubmit={run} className="mt-3 flex gap-2">
        <input
          value={query} onChange={(e) => setQuery(e.target.value)} disabled={readyCount === 0}
          placeholder={readyCount === 0 ? "Upload a report and wait for Ready" : "For example: What was the debt-to-equity ratio?"}
          aria-label="Search query"
          className="min-w-0 flex-1 rounded-md border border-line bg-surface px-3 py-2 text-sm disabled:opacity-60"
        />
        <button disabled={readyCount === 0 || loading || query.trim().length < 2}
                className="inline-flex items-center gap-2 rounded-md bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          <Search className="size-4" aria-hidden /> {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error && <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-loss">{error}</p>}
      {hits && hits.length === 0 && <p className="mt-3 text-sm text-muted">No matching passages found.</p>}
      {hits && hits.length > 0 && (
        <ol className="mt-4 space-y-3">
          {hits.map((h) => (
            <li key={h.chunk_id} className="rounded-lg border border-line bg-surface p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <a href={documentFileUrl(h.document_id, h.page_number)} target="_blank" rel="noreferrer"
                   className="font-medium text-brand hover:underline">
                  {h.document_name}, page {h.page_number}
                </a>
                <span className="text-xs text-muted">
                  {h.kind === "table" ? "Table" : "Text"}
                  {h.section ? ` · ${h.section}` : ""}
                  {h.similarity !== null ? ` · similarity ${(h.similarity * 100).toFixed(0)}%` : ""}
                  {` · ${h.matched_by.join(" + ")}`}
                </span>
              </div>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap font-sans text-sm leading-relaxed">{h.content}</pre>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
