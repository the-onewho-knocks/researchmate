import type { ComponentResult } from "../types";
import CriterionRow from "./CriterionRow";

function scoreClass(score: number | null): string {
  if (score === null) return "na";
  if (score >= 75) return "good";
  if (score >= 50) return "mid";
  return "low";
}

interface Props {
  components: ComponentResult[];
  onJump?: (block: number, id: string) => void;
}

export default function ChecklistGrid({ components, onJump }: Props) {
  return (
    <div className="grid">
      {components.map((c) => (
        <section className="card" key={c.key}>
          <header>
            <div>
              <h3>{c.name}</h3>
              <small>{c.acronym}</small>
            </div>
            <div className={`score ${scoreClass(c.score)}`}>
              {c.score === null ? "–" : `${c.score.toFixed(0)}%`}
              <small>{(c.coverage * 100).toFixed(0)}% assessed</small>
            </div>
          </header>
          <ul>
            {c.verdicts.map((v) => (
              <CriterionRow key={v.id} v={v} onJump={onJump} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
