import type { ChecklistItem } from "../lib/todo";

interface Props {
  items: ChecklistItem[];
  done: Set<string>;
  onToggle: (id: string) => void;
  onJump: (block: number, id: string) => void;
}

function Item({ it, done, onToggle, onJump }: { it: ChecklistItem } & Omit<Props, "items">) {
  const ticked = it.resolved || done.has(it.id);
  return (
    <li className={`todo ${ticked ? "ticked" : ""}`}>
      <label>
        <input
          type="checkbox"
          checked={ticked}
          disabled={it.resolved}
          onChange={() => onToggle(it.id)}
        />
        <span className="tname">
          <span className="cid">{it.id}</span> {it.name}
        </span>
      </label>
      {!ticked && (
        <>
          <div className="chips">
            <span className={`chip impact-${it.impact}`}>impact {it.impact}</span>
            <span className={`chip effort-${it.effort}`}>effort {it.effort}</span>
          </div>
          <p className="tsug">{it.suggestion}</p>
          {it.block !== null && (
            <button className="link" onClick={() => onJump(it.block as number, it.id)}>
              Show in text →
            </button>
          )}
        </>
      )}
      {it.resolved && <small className="fixed">Fixed in this draft</small>}
    </li>
  );
}

export default function TodoSidebar({ items, done, onToggle, onJump }: Props) {
  const fixes = items.filter((i) => i.status === "fail" || i.resolved);
  const checks = items.filter((i) => i.status === "needs_review" && !i.resolved);
  const tickedFixes = fixes.filter((i) => i.resolved || done.has(i.id)).length;
  const pct = fixes.length ? Math.round((100 * tickedFixes) / fixes.length) : 100;

  return (
    <aside className="sidebar">
      <h3>To fix</h3>
      <div className="progress" aria-label={`${pct}% done`}>
        <div style={{ width: `${pct}%` }} />
      </div>
      <small className="plabel">
        {tickedFixes} of {fixes.length} done · best value first
      </small>

      {fixes.length === 0 ? (
        <p className="empty">Nothing failed automatically. Check the items below yourself.</p>
      ) : (
        <ul>
          {fixes.map((it) => (
            <Item key={it.id} it={it} done={done} onToggle={onToggle} onJump={onJump} />
          ))}
        </ul>
      )}

      {checks.length > 0 && (
        <details>
          <summary>To check yourself ({checks.length})</summary>
          <ul>
            {checks.map((it) => (
              <Item key={it.id} it={it} done={done} onToggle={onToggle} onJump={onJump} />
            ))}
          </ul>
        </details>
      )}
    </aside>
  );
}
