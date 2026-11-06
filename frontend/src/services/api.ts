import axios from "axios";
import type { HealthStatus } from "../types";

// Same-origin: Vite proxies /api in dev, nginx proxies it in Docker. No secrets live in the frontend.
export const http = axios.create({ baseURL: "/api", timeout: 30_000 });

export const getHealth = () => http.get<HealthStatus>("/health").then((r) => r.data);
