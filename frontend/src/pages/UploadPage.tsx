import { useState } from "react";
import { evaluate, uploadFile } from "../api/client";
import UploadDropzone from "../components/UploadDropzone";
import type { EvaluationReport } from "../types";

interface Props {
  llmAvailable: boolean;
  onDone: (report: EvaluationReport, filename: string) => void;
}

export default function UploadPage({ llmAvailable, onDone }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [coach, setCoach] = useState(false);
  const [suggest, setSuggest] = useState(true);
  const [busy, setBusy] = useState<"" | "uploading" | "evaluating">("");
  const [error, setError] = useState("");

  const run = async () => {
    if (!file) return;
    setError("");
    try {
      setBusy("uploading");
      const up = await uploadFile(file);
      setBusy("evaluating");
      const report = await evaluate(up.document_id, coach && llmAvailable, suggest && llmAvailable);
      onDone(report, up.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy("");
    }
  };

  const off = !llmAvailable || !!busy;

  return (
    <div className="upload">
      <h2>Check your paper draft against the checklist</h2>
      <p className="lead">
        Upload a PDF, Word or LaTeX draft. Counting and cue-phrase checks run locally; judgment
        criteria go to an AI judge when one is configured.
      </p>

      <UploadDropzone file={file} disabled={!!busy} onFile={setFile} />

      <label className={`check ${llmAvailable ? "" : "disabled"}`}>
        <input
          type="checkbox"
          checked={suggest && llmAvailable}
          disabled={off}
          onChange={(e) => setSuggest(e.target.checked)}
        />
        Suggest a concrete fix for each failed item {llmAvailable ? "" : "(needs GEMINI_API_KEY)"}
      </label>
      <label className={`check ${llmAvailable ? "" : "disabled"}`}>
        <input
          type="checkbox"
          checked={coach && llmAvailable}
          disabled={off}
          onChange={(e) => setCoach(e.target.checked)}
        />
        Add short coaching feedback {llmAvailable ? "" : "(needs GEMINI_API_KEY)"}
      </label>

      {error && <div className="error">{error}</div>}

      <button className="primary" disabled={!file || !!busy} onClick={run}>
        {busy === "uploading" && "Uploading…"}
        {busy === "evaluating" && "Evaluating… this can take a minute"}
        {!busy && "Evaluate paper"}
      </button>
    </div>
  );
}
