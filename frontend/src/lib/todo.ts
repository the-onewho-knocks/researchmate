import type { Comparison, EvaluationReport, TodoItem } from "../types";

export interface ChecklistItem extends TodoItem {
  /** Fixed since the previous draft (auto-ticked). */
  resolved: boolean;
}

/**
 * Items for the sticky checklist: everything still open in the current draft,
 * plus the items from the previous draft that this draft fixed.
 */
export function buildItems(
  report: EvaluationReport,
  previous: EvaluationReport | null,
  comparison: Comparison | null,
): ChecklistItem[] {
  const open: ChecklistItem[] = report.todo.map((t) => ({ ...t, resolved: false }));
  if (!previous || !comparison) return open;

  const resolved = new Set(comparison.resolved_ids);
  const openIds = new Set(open.map((t) => t.id));
  const fixed: ChecklistItem[] = previous.todo
    .filter((t) => resolved.has(t.id) && !openIds.has(t.id))
    .map((t) => ({ ...t, resolved: true }));
  return [...open, ...fixed];
}

const KEY = (lineage: string) => `strawberry.done.${lineage}`;

export function loadDone(lineage: string): Set<string> {
  try {
    const raw = localStorage.getItem(KEY(lineage));
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

export function saveDone(lineage: string, done: Set<string>): void {
  try {
    localStorage.setItem(KEY(lineage), JSON.stringify([...done]));
  } catch {
    /* storage can be unavailable; ticks then last for this session only */
  }
}
