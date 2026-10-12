"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

/**
 * TanStack Query provider (v5).
 *
 * Defaults tuned for an operational dashboard talking to a local/live API:
 * - staleTime 30s: navigating away and back paints instantly from cache
 * - refetchOnWindowFocus off: dashboards poll explicitly (60s intervals)
 * - retry 1: transient blips recover, hard failures surface fast
 */
export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 5 * 60_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
