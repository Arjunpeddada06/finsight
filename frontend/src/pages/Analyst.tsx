import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { Loader2, Plus, Send } from "lucide-react";
import ChatMessage from "../components/ChatMessage";
import { useToast } from "../components/Toast";
import { useDocuments } from "../hooks/useDocuments";
import { sendChat } from "../services/chat";
import { errorMessage } from "../services/documents";
import type { ChatTurn } from "../types";

const SUGGESTED = [
  "What was the company's revenue in 2025?",
  "What was the net profit?",
  "Compare revenue between 2024 and 2025.",
  "What were the major expenses?",
  "What is the company's debt?",
  "What is the profit margin?",
  "Summarize the financial performance.",
  "Which business segment generated the highest revenue?",
  "What risks are mentioned in the report?",
  "What are the company's future growth plans?",
];

export default function Analyst() {
  const { documents, loading } = useDocuments();
  const readyCount = documents.filter((d) => d.status === "ready").length;
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const toast = useToast();

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, sending]);

  async function send(text: string) {
    const message = text.trim();
    if (message.length < 2 || sending) return;
    setInput("");
    setSending(true);
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "user", content: message }]);
    try {
      const res = await sendChat(message, conversationId);
      setConversationId(res.conversation_id);
      setTurns((t) => [...t, { id: res.message_id, role: "assistant", content: res.answer, sources: res.sources, refused: res.refused, tool_used: res.tool_used }]);
    } catch (e) {
      const msg = errorMessage(e);
      toast("error", msg);
      setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content: `Sorry, I couldn't answer that. ${msg}`, refused: true }]);
    } finally {
      setSending(false);
    }
  }

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }
  };

  const newChat = () => { setTurns([]); setConversationId(undefined); setInput(""); };

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-3xl flex-col md:h-[calc(100vh-4rem)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">AI Analyst</h1>
          <p className="mt-1 text-sm text-muted">Answers come only from your uploaded reports and always cite the page.</p>
        </div>
        {turns.length > 0 && (
          <button onClick={newChat} className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-sm hover:bg-paper">
            <Plus className="size-4" aria-hidden /> New chat
          </button>
        )}
      </div>

      <div className="mt-4 flex-1 space-y-4 overflow-y-auto pr-1" aria-live="polite">
        {turns.length === 0 && (
          <div className="rounded-lg border border-line bg-surface p-5">
            {!loading && readyCount === 0 ? (
              <p className="text-sm">
                There are no processed reports yet. <Link to="/documents" className="font-medium text-brand underline">Upload a report</Link> and wait for Ready, then ask your question here.
              </p>
            ) : (
              <>
                <p className="text-sm font-medium">Try a question</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SUGGESTED.map((q) => (
                    <button key={q} onClick={() => send(q)} disabled={readyCount === 0}
                            className="rounded-full border border-line bg-paper px-3 py-1.5 text-left text-xs hover:border-brand disabled:opacity-50">
                      {q}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
        {turns.map((t) => <ChatMessage key={t.id} turn={t} />)}
        {sending && (
          <div className="flex items-center gap-2 text-sm text-muted" role="status">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Searching your reports…
          </div>
        )}
        <div ref={bottom} />
      </div>

      <div className="mt-3">
        <div className="flex items-end gap-2 rounded-lg border border-line bg-surface p-2">
          <textarea
            value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} rows={2} maxLength={2000}
            disabled={readyCount === 0} aria-label="Your question"
            placeholder={readyCount === 0 ? "Upload a report to start" : "Ask about revenue, profit, debt, risks…"}
            className="min-h-10 flex-1 resize-none bg-transparent px-2 py-1 text-sm outline-none disabled:opacity-60"
          />
          <button onClick={() => send(input)} disabled={sending || input.trim().length < 2 || readyCount === 0} aria-label="Send"
                  className="rounded-md bg-brand p-2.5 text-white disabled:opacity-50">
            <Send className="size-4" aria-hidden />
          </button>
        </div>
        <p className="mt-1.5 text-center text-xs text-muted">FinSight AI is a research assistant and does not give investment advice.</p>
      </div>
    </div>
  );
}
