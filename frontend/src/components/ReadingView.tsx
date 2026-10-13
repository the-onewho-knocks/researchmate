import { useEffect, useMemo } from "react";
import type { EvaluationReport, Jump, Paragraph, Status, Verdict } from "../types";

const SECTION_NAMES: Record<string, string> = {
  title: "Title",
  abstract: "Abstract",
  introduction: "Introduction",
  related_work: "Related Work",
  methods: "Methods",
  results: "Results",
  discussion: "Discussion",
  conclusion: "Conclusion",
  references: "References",
};

const ICON: Record<Status, string> = { pass: "✓", fail: "✗", needs_review: "?", could_not_assess: "–" };

interface Group {
  key: string;
  labels: string[];
  paras: Paragraph[];
}

function groupParagraphs(paras: Paragraph[]): Group[] {
  const groups: Group[] = [];
  for (const p of paras) {
    const key = p.sections.join("+") || "other";
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.paras.push(p);
    else groups.push({ key, labels: p.sections, paras: [p] });
  }
  return groups;
}

/** Wrap the evidence quotes that really occur in the paragraph text in <mark>. */
function Highlighted({ text, marks }: { text: string; marks: Verdict[] }) {
  const lower = text.toLowerCase();
  const ranges: { start: number; end: number; status: Status; id: string }[] = [];
  for (const v of marks) {
    if (!v.evidence) continue;
    const needle = v.evidence.replace(/…$/, "").trim().toLowerCase();
    const at = needle ? lower.indexOf(needle) : -1;
    if (at >= 0) ranges.push({ start: at, end: at + needle.length, status: v.status, id: v.id });
  }
  ranges.sort((a, b) => a.start - b.start);

  const parts: JSX.Element[] = [];
  let pos = 0;
  for (const r of ranges) {
    if (r.start < pos) continue; // skip overlaps
    if (r.start > pos) parts.push(<span key={`t${pos}`}>{text.slice(pos, r.start)}</span>);
    parts.push(
      <mark key={`m${r.start}`} className={r.status} title={r.id}>
        {text.slice(r.start, r.end)}
      </mark>,
    );
    pos = r.end;
  }
  parts.push(<span key="rest">{text.slice(pos)}</span>);
  return <>{parts}</>;
}

function scrollToBlock(block: number) {
  document.getElementById(`p-${block}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
}

interface Props {
  report: EvaluationReport;
  jump: Jump | null;
}

export default function ReadingView({ report, jump }: Props) {
  const groups = useMemo(() => groupParagraphs(report.paragraphs), [report.paragraphs]);
  const verdicts = useMemo(() => report.components.flatMap((c) => c.verdicts), [report.components]);

  const byBlock = useMemo(() => {
    const m = new Map<number, Verdict[]>();
    for (const v of verdicts) {
      if (v.block === null) continue;
      m.set(v.block, [...(m.get(v.block) ?? []), v]);
    }
    return m;
  }, [verdicts]);

  useEffect(() => {
    if (jump) scrollToBlock(jump.block);
  }, [jump]);

  return (
    <div className="reading">
      <p className="legend">
        <mark className="pass">evidence found</mark> <mark className="fail">problem</mark>{" "}
        <mark className="needs_review">needs your check</mark> — failed items point to the start of the section
        where the fix belongs.
      </p>
      {groups.map((g, gi) => {
        const crit = verdicts.filter((v) => v.section && g.labels.includes(v.section));
        const title = g.labels.map((l) => SECTION_NAMES[l] ?? l).join(" & ") || "Other";
        return (
          <section className="rgroup" key={`${g.key}-${gi}`}>
            <div className="rtext">
              <h3 className="rtitle">{title}</h3>
              {g.paras.map((p) => {
                const marks = byBlock.get(p.i) ?? [];
                const worst = marks.some((m) => m.status === "fail")
                  ? "fail"
                  : marks.some((m) => m.status === "needs_review")
                    ? "needs_review"
                    : marks.length
                      ? "pass"
                      : "";
                const focus = jump?.block === p.i ? "focus" : "";
                const body = <Highlighted text={p.text} marks={marks} />;
                return (
                  <div id={`p-${p.i}`} key={p.i} className={`para ${p.kind} ${worst} ${focus}`}>
                    {p.kind === "heading" ? <h4>{body}</h4> : <p>{body}</p>}
                    {marks.length > 0 && (
                      <div className="pchips">
                        {marks.map((m) => (
                          <span key={m.id} className={`pchip ${m.status}`} title={m.name}>
                            {m.id}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <aside className="rcrit">
              {crit.length === 0 ? (
                <small className="empty">No checklist items for this part.</small>
              ) : (
                <ul>
                  {crit.map((v) => (
                    <li key={v.id} className={`rc ${v.status} ${jump?.id === v.id ? "focus" : ""}`}>
                      <div className="rc-head">
                        <span className={`icon ${v.status}`}>{ICON[v.status]}</span>
                        <span>
                          <span className="cid">{v.id}</span> {v.name}
                        </span>
                      </div>
                      {v.suggestion && v.status !== "pass" && <p className="rc-sug">{v.suggestion}</p>}
                      {v.block !== null && (
                        <button className="link" onClick={() => scrollToBlock(v.block as number)}>
                          {v.status === "pass" ? "Show evidence" : "Go to place"}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </aside>
          </section>
        );
      })}
    </div>
  );
}
