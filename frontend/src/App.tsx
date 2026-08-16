import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { router } from "@/router";
import { ResearchModeProvider } from "@/contexts/ResearchMode";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ResearchModeProvider>
        <RouterProvider router={router} future={{ v7_startTransition: true }} />
      </ResearchModeProvider>
    </QueryClientProvider>
  );
}
