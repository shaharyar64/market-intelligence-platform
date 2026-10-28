"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { friendlyError, isAbort } from "@/lib/foodIntelligence";

export type Resource<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
};

export function useAsyncResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[],
  { enabled = true }: { enabled?: boolean } = {},
): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [reloadKey, setReloadKey] = useState(0);

  const fetcherRef = useRef(fetcher);
  useEffect(() => { fetcherRef.current = fetcher; });

  useEffect(() => {
    if (!enabled) return;
    const ac = new AbortController();
    setData(null);
    setError(null);
    setLoading(true);
    fetcherRef.current(ac.signal)
      .then((value) => {
        if (ac.signal.aborted) return;
        setData(value);
        setLoading(false);
      })
      .catch((e) => {
        if (ac.signal.aborted || isAbort(e)) return;
        console.error("Request failed", e);
        setError(friendlyError(e));
        setLoading(false);
      });
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, reloadKey]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  if (!enabled) return { data: null, loading: false, error: null, reload };
  const settling = data === null && error === null;
  return { data, loading: loading || settling, error, reload };
}
