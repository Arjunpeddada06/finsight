import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { errorMessage, uploadDocument } from "../services/documents";
import { useToast } from "./Toast";

interface Upload { key: string; name: string; percent: number; error?: string }

export default function UploadDropzone({ onUploaded }: { onUploaded: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const toast = useToast();

  const patch = (key: string, change: Partial<Upload>) =>
    setUploads((cur) => cur.map((u) => (u.key === key ? { ...u, ...change } : u)));

  async function handleFiles(files: FileList | File[]) {
    for (const file of Array.from(files)) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        toast("error", `${file.name} is not a PDF. Only PDF files can be uploaded.`);
        continue;
      }
      const key = `${file.name}-${Date.now()}-${Math.random()}`;
      setUploads((cur) => [...cur, { key, name: file.name, percent: 0 }]);
      try {
        await uploadDocument(file, (percent) => patch(key, { percent }));
        setUploads((cur) => cur.filter((u) => u.key !== key));
        toast("success", `${file.name} uploaded. Processing has started.`);
        onUploaded();
      } catch (err) {
        const message = errorMessage(err);
        patch(key, { error: message });
        toast("error", `${file.name}: ${message}`);
      }
    }
  }

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
        className={`flex flex-col items-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragging ? "border-brand bg-brand-soft" : "border-line bg-surface"
        }`}
      >
        <UploadCloud className="size-8 text-brand" aria-hidden />
        <p className="font-medium">Drop financial reports here</p>
        <p className="text-sm text-muted">Annual reports, quarterly results and statements, PDF up to 50 MB</p>
        <button
          onClick={() => input.current?.click()}
          className="mt-2 rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          Choose PDF files
        </button>
        <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden
          onChange={(e) => { if (e.target.files) handleFiles(e.target.files); e.target.value = ""; }} />
      </div>

      {uploads.length > 0 && (
        <ul className="mt-3 space-y-2">
          {uploads.map((u) => (
            <li key={u.key} className="rounded-md border border-line bg-surface px-4 py-3 text-sm">
              <div className="flex justify-between gap-4">
                <span className="truncate">{u.name}</span>
                <span className={u.error ? "text-loss" : "text-muted"}>{u.error ? "Failed" : `${u.percent}%`}</span>
              </div>
              {u.error ? (
                <div className="mt-1 flex items-center justify-between gap-4 text-xs text-loss">
                  <span>{u.error}</span>
                  <button className="underline" onClick={() => setUploads((c) => c.filter((x) => x.key !== u.key))}>Dismiss</button>
                </div>
              ) : (
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-paper" role="progressbar" aria-valuenow={u.percent} aria-valuemin={0} aria-valuemax={100}>
                  <div className="h-full bg-brand transition-[width]" style={{ width: `${u.percent}%` }} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
