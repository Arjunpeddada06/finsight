import { Loader2 } from "lucide-react";
import type { DocumentStatus } from "../types";

const STYLES: Record<DocumentStatus, { label: string; cls: string; spin?: boolean }> = {
  uploaded: { label: "Uploaded", cls: "bg-paper text-muted", spin: true },
  processing: { label: "Processing", cls: "bg-amber-50 text-amber-800", spin: true },
  extracting: { label: "Extracting", cls: "bg-amber-50 text-amber-800", spin: true },
  embedding: { label: "Embedding", cls: "bg-amber-50 text-amber-800", spin: true },
  ready: { label: "Ready", cls: "bg-brand-soft text-brand" },
  failed: { label: "Failed", cls: "bg-red-50 text-loss" },
};

export default function StatusBadge({ status }: { status: DocumentStatus }) {
  const s = STYLES[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.spin && <Loader2 className="size-3 animate-spin" aria-hidden />}
      {s.label}
    </span>
  );
}
