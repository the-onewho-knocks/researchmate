import type { Comparison, Status } from "../types";

const LABEL: Record<Status, string> = {
  pass: "Met",
  fail: "Not met",
  needs_review: "Needs review",
  could_not_assess: "Not assessed",
};

function fmt(n: number | null, suffix = "%"): string {
  return n === null ? "–" : `${n.toFixed(0)}${suffix}`;
}

function Delta({ d }: { d: number | null }) {
  if (d === null) return <span className="delta">–</span>;
  const cls = d > 0 ? "up" : d < 0 ? "down" : "flat";
  return <span className={`delta ${cls}`}>{d > 0 ? `+${d.toFixed(1)}` : d.toFixed(1)}</span>;
}

export default function ComparisonPanel({ cmp }: { cmp: Comparison }) {
  const order = { improved: 0, regressed: 1, changed: 2 } as const;
  const changes = [...cmp.changes].sort((a, b) => order[a.direction] - order[b.direction]);

  return (
    <div className="compare">
      <div className="summary">
        <div className="big">
          <span>
            {fmt(cmp.overall_before)} → {fmt(cmp.overall_after)}
          </span>
          <small>
            overall score <Delta d={cmp.overall_delta} />
          </small>
        </div>
        <div className="sources">
          <span className="up">{cmp.improved} improved</span>
          <span className="down">{cmp.regressed} got worse</span>
          <span>{cmp.changed} changed to or from "needs review"</span>
          <span>{cmp.unchanged} unchanged</span>
          <span>{cmp.still_failing} still not met</span>
        </div>
      </div>

      <h3>Per component</h3>
      <table className="deltas">
        <tbody>
          {cmp.components.map((c) => (
            <tr key={c.key}>
              <td>{c.name}</td>
              <td>{fmt(c.before)}</td>
              <td>→</td>
              <td>{fmt(c.after)}</td>
              <td>
                <Delta d={c.delta} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>What changed</h3>
      {changes.length === 0 ? (
        <p className="empty">No criterion changed between the two drafts.</p>
      ) : (
        <ul className="changes">
          {changes.map((c) => (
            <li key={c.id} className={c.direction}>
              <span className={`dir ${c.direction}`}>
                {c.direction === "improved" ? "▲" : c.direction === "regressed" ? "▼" : "◆"}
              </span>
              <span className="cname">
                <span className="cid">{c.id}</span> {c.name} <small>({c.component_name})</small>
              </span>
              <span className="tags">
                <span className="tag">{LABEL[c.before]}</span>→<span className="tag">{LABEL[c.after]}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
