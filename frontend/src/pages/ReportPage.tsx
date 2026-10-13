import { useEffect, useMemo, useState } from "react";
import ChecklistGrid from "../components/ChecklistGrid";
import ComparisonPanel from "../components/ComparisonPanel";
import LimitationsBanner from "../components/LimitationsBanner";
import ReadingView from "../components/ReadingView";
import RevisionBox from "../components/RevisionBox";
import TodoSidebar from "../components/TodoSidebar";
import { buildItems, loadDone, saveDone } from "../lib/todo";
import type { Comparison, EvaluationReport, Jump } from "../types";

type Tab = "checklist" | "read" | "compare";

function scoreClass(score: number | null): string {
  if (score === null) return "na";
  if (score >= 75) return "good";   // green
  if (score >= 50) return "mid";    // orange
  return "low";                     // dark red
}

interface Props {
  report: EvaluationReport;
  previous: EvaluationReport | null;
  comparison: Comparison | null;
  lineage: string;
  filename: string;
  llmAvailable: boolean;
  onReset: () => void;
  onRevised: (report: EvaluationReport, filename: string, comparison: Comparison) => void;
}

export default function ReportPage({
  report,
  previous,
  comparison,
  lineage,
  filename,
  llmAvailable,
  onReset,
  onRevised,
}: Props) {
  const [tab, setTab] = useState<Tab>(comparison ? "compare" : "checklist");
  const [jump, setJump] = useState<Jump | null>(null);
  const [done, setDone] = useState<Set<string>>(() => loadDone(lineage));

  // a new revision lands on the comparison first
  useEffect(() => {
    if (comparison) setTab("compare");
  }, [comparison]);

  const items = useMemo(() => buildItems(report, previous, comparison), [report, previous, comparison]);

  const toggle = (id: string) => {
    const next = new Set(done);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setDone(next);
    saveDone(lineage, next);
  };

  const onJump = (block: number, id?: string) => {
    setJump({ block, id, nonce: Date.now() });
    setTab("read");
  };

  const sc = report.source_counts;
  return (
    <div className="report">
      <div className="report-head">
        <div>
          <h2>{filename}</h2>
          <small>
            {report.file_type.toUpperCase()} · framework v{report.framework_version}
            {report.cached && " · cached result"}
          </small>
        </div>
        <button onClick={onReset}>New paper</button>
      </div>

      <div className="summary">
        <div className="big">
    <span className={scoreClass(report.overall_score)}>
      {report.overall_score === null ? "–" : `${report.overall_score.toFixed(0)}%`}
    </span>
          <small>overall · {(report.coverage * 100).toFixed(0)}% of criteria assessed</small>
        </div>
        <div className="sources">
          <span>Decided by rules: {sc.rule ?? 0}</span>
          <span>ML: {sc.ml ?? 0}</span>
          <span>AI: {sc.llm ?? 0}</span>
          <span>Needs your check: {sc.unresolved ?? 0}</span>
        </div>
      </div>

      {report.coach_feedback && (
        <div className="coach">
          <strong>Coach</strong>
          <p>{report.coach_feedback}</p>
        </div>
      )}

      <LimitationsBanner items={report.limitations} />

      <div className="layout">
        <div className="main">
          <nav className="tabs" role="tablist">
            <button className={tab === "checklist" ? "active" : ""} onClick={() => setTab("checklist")}>
              Checklist
            </button>
            <button className={tab === "read" ? "active" : ""} onClick={() => setTab("read")}>
              Read along
            </button>
            {comparison && (
              <button className={tab === "compare" ? "active" : ""} onClick={() => setTab("compare")}>
                Compared to previous draft
              </button>
            )}
          </nav>

          {tab === "checklist" && <ChecklistGrid components={report.components} onJump={onJump} />}
          {tab === "read" && <ReadingView report={report} jump={jump} />}
          {tab === "compare" && comparison && <ComparisonPanel cmp={comparison} />}

          <RevisionBox before={report} llmAvailable={llmAvailable} onDone={onRevised} />

          {report.usage.calls > 0 && (
            <p className="usage">
              {report.usage.calls} AI calls · {report.usage.input_tokens} in / {report.usage.output_tokens} out
              tokens · {report.usage.model}
            </p>
          )}
        </div>

        <TodoSidebar items={items} done={done} onToggle={toggle} onJump={onJump} />
      </div>
    </div>
  );
}
