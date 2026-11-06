import { http } from "./api";
import type { SearchResponse } from "../types";

export const searchDocuments = (query: string, documentIds?: string[], topK = 5) =>
  http.post<SearchResponse>("/search", { query, document_ids: documentIds, top_k: topK }).then((r) => r.data);
