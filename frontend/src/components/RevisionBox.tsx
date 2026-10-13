import { useState } from "react";
import { compare, evaluate, uploadFile } from "../api/client";
import type { Comparison, EvaluationReport } from "../types";
import UploadDropzone from "./UploadDropzone";

interface Props {
  before: EvaluationReport;
  llmAvailable: boolean;
  onDone: (report: EvaluationReport, filename: string, comparison: Comparison) => void;
}

export default function RevisionBox({ before, llmAvailable, onDone }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    if (!file) return;
    setError("");
    setBusy(true);
    try {
      const up = await uploadFile(file);
      const after = await evaluate(up.document_id, false, llmAvailable);
      const cmp = await compare(before.document_id, after.document_id);
      onDone(after, up.filename, cmp);
      setFile(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="revision">
      <h3>Revised your draft?</h3>
      <p className="lead">Upload the new version to see which items you fixed and how the score moved.</p>
      <UploadDropzone file={file} disabled={busy} onFile={setFile} />
      {error && <div className="error">{error}</div>}
      <button className="primary" disabled={!file || busy} onClick={run}>
        {busy ? "Re-checking…" : "Re-check revised draft"}
      </button>
    </div>
  );
}
