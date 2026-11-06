import axios from "axios";
import { http } from "./api";
import type { DocumentDetail, DocumentList, FinDocument } from "../types";

export const listDocuments = (page = 1, pageSize = 50) =>
  http.get<DocumentList>("/documents", { params: { page, page_size: pageSize } }).then((r) => r.data);

export const getDocument = (id: string) => http.get<DocumentDetail>(`/documents/${id}`).then((r) => r.data);

export const uploadDocument = (file: File, onProgress: (percent: number) => void) => {
  const form = new FormData();
  form.append("file", file);
  return http
    .post<FinDocument>("/documents/upload", form, {
      timeout: 5 * 60_000,
      onUploadProgress: (e) => e.total && onProgress(Math.round((e.loaded / e.total) * 100)),
    })
    .then((r) => r.data);
};

export const deleteDocument = (id: string) => http.delete(`/documents/${id}`);
export const reprocessDocument = (id: string) => http.post<FinDocument>(`/documents/${id}/process`).then((r) => r.data);

/** URL that opens the original PDF; most browsers honour #page=N. */
export const documentFileUrl = (id: string, page?: number) => `/api/documents/${id}/file${page ? `#page=${page}` : ""}`;

/** Turns any API failure into a sentence a user can act on. */
export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return "Can't reach the server. Check that the backend is running.";
    const detail = err.response.data?.detail;
    if (typeof detail === "string") return detail;
    if (err.response.status === 429) return "Too many requests. Wait a moment and try again.";
    if (err.response.status === 422) return "The request was not valid.";
  }
  return "Something went wrong. Try again.";
}
