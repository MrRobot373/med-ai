import { AlertTriangle } from "lucide-react";
import { isRouteErrorResponse, useRouteError } from "react-router";
import { Button } from "@/components/ui";

export function RouteError() {
  const error = useRouteError();
  const message = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : error instanceof Error ? error.message : "Unknown error";
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-xl bg-danger-soft text-danger"><AlertTriangle /></div>
      <div>
        <h1 className="text-lg font-semibold">Something went wrong</h1>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">{message}</p>
      </div>
      <Button variant="secondary" onClick={() => window.location.assign("/")}>Back to home</Button>
    </div>
  );
}
