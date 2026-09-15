import { createRoot } from "react-dom/client";

import { App } from "./App";
import { busyWait, parseInject } from "./inject";
import "./styles.css";

const inject = parseInject(location.search);

if (inject?.type === "script-delay") busyWait(inject.size);

createRoot(document.getElementById("root")!).render(<App inject={inject} />);

if (inject?.type === "long-task") {
  requestAnimationFrame(() => setTimeout(() => busyWait(inject.size), 0));
}
