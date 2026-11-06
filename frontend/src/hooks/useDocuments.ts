import { useCallback, useEffect, useRef, useState } from "react";
import { listDocuments } from "../services/documents";
import type { DocumentStatus, FinDocument } from "../types";

const IN_PROGRESS: DocumentStatus[] = ["uploaded", "processing", "extracting", "embedding"];
const POLL_MS = 2000;

/** Loads documents and keeps polling while any of them is still being processed. */
export function useDocuments() {
  const [documents, setDocuments] = useState<FinDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const timer = useRef<number>();

  const refresh = useCallback(async () => {
    try {
      const data = await listDocuments();
      setDocuments(data.items);
      setError(false);
      return data.items;
    } catch {
      setError(true);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      const items = await refresh();
      if (cancelled) return;
      const busy = items?.some((d) => IN_PROGRESS.includes(d.status));
      timer.current = window.setTimeout(tick, busy ? POLL_MS : 10_000);
    };
    tick();
    return () => {
      cancelled = true;
      window.clearTimeout(timer.current);
    };
  }, [refresh]);

  return { documents, loading, error, refresh };
}
