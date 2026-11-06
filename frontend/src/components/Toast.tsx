import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { AlertCircle, CheckCircle2, X } from "lucide-react";

type Kind = "success" | "error";
interface ToastItem { id: number; kind: Kind; message: string }

const ToastContext = createContext<(kind: Kind, message: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = (id: number) => setItems((cur) => cur.filter((t) => t.id !== id));
  const push = useCallback((kind: Kind, message: string) => {
    const id = Date.now() + Math.random();
    setItems((cur) => [...cur, { id, kind, message }]);
    window.setTimeout(() => dismiss(id), kind === "error" ? 8000 : 4000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className="flex items-start gap-3 rounded-md border border-line bg-surface p-3 text-sm shadow-md">
            {t.kind === "success" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-gain" /> : <AlertCircle className="mt-0.5 size-4 shrink-0 text-loss" />}
            <p className="flex-1">{t.message}</p>
            <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="text-muted hover:text-ink"><X className="size-4" /></button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
