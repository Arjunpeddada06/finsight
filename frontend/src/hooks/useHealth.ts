import { useEffect, useState } from "react";
import { getHealth } from "../services/api";
import type { HealthStatus } from "../types";

export function useHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setUnreachable(true));
  }, []);

  return { health, unreachable };
}
