import type { Run } from "./schema.js";

export function measurementIssues(run: Run): string[] {
  const issues: string[] = [];
  if (run.error) issues.push(run.error);
  if (run.failedRequests == null) issues.push("network status unknown");
  else if (run.failedRequests > 0) issues.push(`${run.failedRequests} failed requests`);
  for (const metric of ["fcp", "lcp", "tbt", "cls"] as const) {
    const value = run.metrics[metric];
    if (value == null || !Number.isFinite(value) || value < 0) issues.push(`invalid ${metric}`);
  }
  return issues;
}
