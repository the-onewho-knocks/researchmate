import type { Comparison, EvaluationReport, Health, UploadResponse } from "../types";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.message) message = body.message;
      else if (body?.detail) message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep default message */
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<Health> {
  return handle<Health>(await fetch("/api/health"));
}

export async function uploadFile(file: File): Promise<{ document_id: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);
  return handle<UploadResponse>(await fetch("/api/uploads", { method: "POST", body: form }));
}

export async function evaluate(documentId: string, coach: boolean, suggest = true): Promise<EvaluationReport> {
  return handle<EvaluationReport>(
    await fetch("/api/evaluations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: documentId, coach, suggest }),
    }),
  );
}

export async function compare(beforeId: string, afterId: string): Promise<Comparison> {
  return handle<Comparison>(
    await fetch("/api/evaluations/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ before_id: beforeId, after_id: afterId }),
    }),
  );
}
