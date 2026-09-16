import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";

import { busyWait, parseInject, type Inject } from "./inject";
import "./styles.css";

/** Shared entry point of every demo page: applies the url-driven injections around the render. */
export function mount(render: (inject: Inject | null) => ReactNode): void {
  const inject = parseInject(location.search);

  if (inject?.type === "script-delay") busyWait(inject.size);

  createRoot(document.getElementById("root")!).render(render(inject));

  if (inject?.type === "long-task") {
    requestAnimationFrame(() => setTimeout(() => busyWait(inject.size), 0));
  }
}
