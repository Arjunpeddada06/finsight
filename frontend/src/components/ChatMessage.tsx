import { Copy } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { documentFileUrl } from "../services/documents";
import type { ChatTurn } from "../types";
import { useToast } from "./Toast";

/** The model cites as [S1]; readers see [1]. */
const display = (text: string) => text.replace(/\[S(\d+)\]/g, "[$1]");

export default function ChatMessage({ turn }: { turn: ChatTurn }) {
  const toast = useToast();

  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand px-4 py-2.5 text-sm text-white">{turn.content}</p>
      </div>
    );
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(display(turn.content));
      toast("success", "Answer copied.");
    } catch {
      toast("error", "Couldn't copy. Select the text and copy it manually.");
    }
  }

  return (
    <div className="max-w-[92%]">
      {turn.tool_used && <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted">Tool: {turn.tool_used.replaceAll("_", " ")}</div>}
      <div className={`rounded-2xl rounded-bl-sm border px-4 py-3 text-sm leading-relaxed ${turn.refused ? "border-amber-200 bg-amber-50" : "border-line bg-surface"}`}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            p: (props) => <p className="mb-2 last:mb-0" {...props} />,
            ul: (props) => <ul className="mb-2 list-disc pl-5" {...props} />,
            ol: (props) => <ol className="mb-2 list-decimal pl-5" {...props} />,
            table: (props) => <div className="my-2 overflow-x-auto"><table className="min-w-full border-collapse text-sm" {...props} /></div>,
            th: (props) => <th className="border border-line bg-paper px-3 py-1.5 text-left font-medium" {...props} />,
            td: (props) => <td className="border border-line px-3 py-1.5 tabular-nums" {...props} />,
          }}
        >
          {display(turn.content)}
        </ReactMarkdown>

        {turn.sources && turn.sources.length > 0 && (
          <div className="mt-3 border-t border-line pt-2">
            <div className="text-xs font-medium text-muted">Sources</div>
            <ul className="mt-1 space-y-1">
              {turn.sources.map((s) => (
                <li key={s.label} className="text-xs">
                  <span className="text-muted">[{s.label}] </span>
                  <a href={documentFileUrl(s.document_id, s.page_number)} target="_blank" rel="noreferrer"
                     title={s.snippet ?? undefined} className="font-medium text-brand hover:underline">
                    {s.document_name}, page {s.page_number}
                  </a>
                  {s.section && <span className="text-muted"> · {s.section}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <button onClick={copy} className="mt-1 inline-flex items-center gap-1 text-xs text-muted hover:text-ink" aria-label="Copy answer">
        <Copy className="size-3" aria-hidden /> Copy
      </button>
    </div>
  );
}
