import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
export function useAction() {
  const [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const cache = useQueryClient();
  async function run(fn: () => Promise<unknown>, done?: () => void) {
    setError(null);
    setBusy(true);
    try {
      await fn();
      await cache.invalidateQueries();
      done?.();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return { run, error, busy, setError };
}
