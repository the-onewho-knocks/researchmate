import { useEffect, useState } from "react";
import { getHealth } from "./api/client";
import ReportPage from "./pages/ReportPage";
import UploadPage from "./pages/UploadPage";
import type { Comparison, EvaluationReport, Health } from "./types";

interface Session {
  report: EvaluationReport;
  filename: string;
  previous: EvaluationReport | null;
  comparison: Comparison | null;
  lineage: string;          // id of the first draft; keeps manual ticks across revisions
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          <span className="berry">🍓</span> STRaWBERRY-LLM
        </h1>
        <div className="badges">
          <span className={`badge ${health?.llm_available ? "on" : "off"}`}>
            AI judge {health?.llm_available ? "on" : "off"}
          </span>
          <span className={`badge ${health?.ml_available ? "on" : "off"}`}>
            ML {health?.ml_available ? (health.ml_calibrated ? "trained" : "zero-shot") : "off"}
          </span>
        </div>
      </header>
      <main>
        {session ? (
          <ReportPage
            report={session.report}
            previous={session.previous}
            comparison={session.comparison}
            lineage={session.lineage}
            filename={session.filename}
            llmAvailable={!!health?.llm_available}
            onReset={() => setSession(null)}
            onRevised={(report, filename, comparison) =>
              setSession((s) =>
                s ? { ...s, report, filename, previous: s.report, comparison } : s,
              )
            }
          />
        ) : (
          <UploadPage
            llmAvailable={!!health?.llm_available}
            onDone={(report, filename) =>
              setSession({ report, filename, previous: null, comparison: null, lineage: report.document_id })
            }
          />
        )}
      </main>
    </div>
  );
}
