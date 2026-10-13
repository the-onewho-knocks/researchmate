import { useRef, useState } from "react";

const ACCEPT = ".pdf,.docx,.tex";

interface Props {
  file: File | null;
  disabled?: boolean;
  onFile: (f: File) => void;
}

export default function UploadDropzone({ file, disabled, onFile }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const pick = (f: File | undefined) => {
    if (f && !disabled) onFile(f);
  };

  return (
    <div
      className={`dropzone ${over ? "over" : ""} ${disabled ? "disabled" : ""}`}
      onClick={() => !disabled && input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        pick(e.dataTransfer.files[0]);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
    >
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(e) => pick(e.target.files?.[0])}
      />
      {file ? (
        <>
          <strong>{file.name}</strong>
          <span>{(file.size / 1024 / 1024).toFixed(2)} MB · click to change</span>
        </>
      ) : (
        <>
          <strong>Drop your paper draft here</strong>
          <span>or click to browse · .pdf, .docx or .tex</span>
        </>
      )}
    </div>
  );
}
