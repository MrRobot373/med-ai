import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { AppearanceProvider, useAppearance } from "./appearance";

function ThemedToaster() {
  const { resolvedTheme } = useAppearance();
  return <Toaster theme={resolvedTheme} position="bottom-right" richColors closeButton toastOptions={{ className: "font-sans" }} />;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            refetchOnWindowFocus: false,
            retry: (count, err) => !(err instanceof ApiError && [401, 403, 404].includes(err.status)) && count < 2,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <AppearanceProvider>
        <TooltipProvider delayDuration={250}>
          {children}
          <ThemedToaster />
        </TooltipProvider>
      </AppearanceProvider>
    </QueryClientProvider>
  );
}
