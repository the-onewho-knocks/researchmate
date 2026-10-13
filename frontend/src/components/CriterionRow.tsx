import { useState } from "react";
import type { Status, Verdict } from "../types";

const LABEL: Record<Status, string> = {
  pass: "Met",
  fail: "Not met",
  needs_review: "Needs review",
  could_not_assess: "Not assessed",
};

const ICON: Record<Status, string> = {
  pass: "✓",
  fail: "✗",
  needs_review: "?",
  could_not_assess: "–",
};

const SOURCE: Record<string, string> = {
  rule: "Rule",
  ml: "ML",
  llm: "AI",
};

interface Props {
  v: Verdict;
  onJump?: (block: number, id: string) => void;
}

export default function CriterionRow({ v, onJump }: Props) {
  const [open, setOpen] = useState(false);
  const showSuggestion = v.status !== "pass" && !!v.suggestion;
  const hasDetail = !!(v.evidence || v.note || showSuggestion || v.block !== null);

  return (
    <li className={`criterion ${v.status}`}>
      <button className="row" onClick={() => setOpen(!open)} disabled={!hasDetail}>
        <span className={`icon ${v.status}`}>{ICON[v.status]}</span>
        <span className="cname">
          <span className="cid">{v.id}</span> {v.name}
        </span>
        <span className="tags">
          <span className="tag">{LABEL[v.status]}</span>
          {(v.status === "pass" || v.status === "fail") && (
            <span className="tag muted" title={`confidence ${(v.confidence * 100).toFixed(0)}%`}>
              {SOURCE[v.source]} · {(v.confidence * 100).toFixed(0)}%
            </span>
          )}
        </span>
      </button>
      {open && hasDetail && (
        <div className="detail">
          {v.evidence && <blockquote>{v.evidence}</blockquote>}
          {v.note && <p>{v.note}</p>}
          {showSuggestion && (
            <p className="suggestion">
              <strong>Fix:</strong> {v.suggestion}
            </p>
          )}
          {v.block !== null && onJump && (
            <button className="link" onClick={() => onJump(v.block as number, v.id)}>
              {v.status === "pass" ? "Show evidence in text →" : "Show where to fix it →"}
            </button>
          )}
        </div>
      )}
    </li>
  );
}
