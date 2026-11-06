import { http } from "./api";
import type { ChatResponse } from "../types";

export const sendChat = (message: string, conversationId?: string) =>
  http.post<ChatResponse>("/chat", { message, conversation_id: conversationId }, { timeout: 120_000 }).then((r) => r.data);
