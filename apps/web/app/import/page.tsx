"use client";

import {
  ChangeEvent,
  DragEvent,
  useCallback,
  useRef,
  useState,
} from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const ACCEPTED_EXTENSIONS = [".csv", ".xlsx", ".xls", ".txt"];
const MAX_FILE_SIZE = 20 * 1024 * 1024;

type PreviewResponse = {
  filename: string;
  found: number;
  valid: number;
  invalid: number;
  duplicates: number;
  ready_to_import: number;
  preview: string[];
};

type CommitResponse = {
  status: string;
  filename: string;
  found: number;
  valid: number;
  invalid: number;
  duplicates_in_file: number;
  unique_valid: number;
  inserted: number;
  already_existed: number;
};

type ApiErrorResponse = {
  detail?: string;
};

function getFileExtension(filename: string): string {
  const dotIndex = filename.lastIndexOf(".");

  if (dotIndex === -1) {
    return "";
  }

  return filename.slice(dotIndex).toLowerCase();
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  const unitIndex = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, unitIndex);

  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

async function getErrorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as ApiErrorResponse;

    if (typeof data.detail === "string" && data.detail.trim()) {
      return data.detail;
    }
  } catch {
    // Response ni JSON.
  }

  return `API je vrnil napako ${response.status}.`;
}

export default function ImportPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [result, setResult] = useState<CommitResponse | null>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isImporting, setIsImporting] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const resetResults = useCallback(() => {
    setPreview(null);
    setResult(null);
    setError(null);
  }, []);

  const validateFile = useCallback((file: File): string | null => {
    const extension = getFileExtension(file.name);

    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      return "Podprte so samo CSV, XLSX, XLS in TXT datoteke.";
    }

    if (file.size === 0) {
      return "Izbrana datoteka je prazna.";
    }

    if (file.size > MAX_FILE_SIZE) {
      return "Datoteka je prevelika. Največja dovoljena velikost je 20 MB.";
    }

    return null;
  }, []);

  const selectFile = useCallback(
    (file: File) => {
      const validationError = validateFile(file);

      resetResults();

      if (validationError) {
        setSelectedFile(null);
        setError(validationError);

        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }

        return;
      }

      setSelectedFile(file);
    },
    [resetResults, validateFile],
  );

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    selectFile(file);
  }

  function handleDragEnter(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(true);
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(true);
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();

    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }

    setIsDragging(false);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);

    const file = event.dataTransfer.files?.[0];

    if (!file) {
      return;
    }

    selectFile(file);
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function removeFile() {
    setSelectedFile(null);
    resetResults();

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function createPreview() {
    if (!selectedFile || isPreviewing || isImporting) {
      return;
    }

    setIsPreviewing(true);
    setError(null);
    setPreview(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${API_URL}/imports/preview`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(await getErrorMessage(response));
      }

      const data = (await response.json()) as PreviewResponse;
      setPreview(data);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Predogleda ni bilo mogoče ustvariti.";

      setError(
        message === "Failed to fetch"
          ? "Povezava z API-jem ni uspela. Preveri, ali backend deluje na portu 8000."
          : message,
      );
    } finally {
      setIsPreviewing(false);
    }
  }

  async function commitImport() {
    if (!selectedFile || isImporting || isPreviewing) {
      return;
    }

    setIsImporting(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${API_URL}/imports/commit`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(await getErrorMessage(response));
      }

      const data = (await response.json()) as CommitResponse;
      setResult(data);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Uvoz ni uspel.";

      setError(
        message === "Failed to fetch"
          ? "Povezava z API-jem ni uspela. Preveri, ali backend deluje na portu 8000."
          : message,
      );
    } finally {
      setIsImporting(false);
    }
  }

  const isBusy = isPreviewing || isImporting;

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">Import</p>
          <h1>Import emails</h1>
          <p className="muted">
            Upload a CSV, XLSX, XLS or TXT file, verify the data and save it to your contacts.
          </p>
        </div>
      </header>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Upload file</h2>
            <p className="muted">
              CSV, XLSX, XLS, and TXT files up to 20 MB in size are supported.
            </p>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls,.txt"
          onChange={handleFileInputChange}
          style={{ display: "none" }}
        />

        <div
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={openFilePicker}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              openFilePicker();
            }
          }}
          style={{
            marginTop: 24,
            minHeight: 220,
            border: isDragging
              ? "2px solid var(--accent, #6366f1)"
              : "2px dashed rgba(148, 163, 184, 0.35)",
            borderRadius: 18,
            background: isDragging
              ? "rgba(99, 102, 241, 0.08)"
              : "rgba(148, 163, 184, 0.04)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 32,
            textAlign: "center",
            cursor: "pointer",
            transition: "border-color 160ms ease, background 160ms ease",
          }}
        >
          <div>
            <div
              style={{
                width: 54,
                height: 54,
                margin: "0 auto 16px",
                borderRadius: 16,
                display: "grid",
                placeItems: "center",
                background: "rgba(99, 102, 241, 0.12)",
                fontSize: 25,
              }}
            >
              ↑
            </div>

            <h3 style={{ marginBottom: 8 }}>
              {isDragging
                ? "Drop file here"
                : "Drag the file into this field"}
            </h3>

            <p className="muted" style={{ marginBottom: 18 }}>
              or select it from your computer
            </p>

            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                openFilePicker();
              }}
              disabled={isBusy}
            >
              Select file
            </button>
          </div>
        </div>

        {selectedFile && (
          <div
            style={{
              marginTop: 20,
              padding: 18,
              border: "1px solid rgba(148, 163, 184, 0.2)",
              borderRadius: 14,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <div>
              <strong>{selectedFile.name}</strong>
              <p className="muted" style={{ margin: "5px 0 0" }}>
                {formatFileSize(selectedFile.size)}
              </p>
            </div>

            <div
              style={{
                display: "flex",
                gap: 10,
                flexWrap: "wrap",
              }}
            >
              <button
                type="button"
                onClick={createPreview}
                disabled={isBusy}
              >
                {isPreviewing ? "Checking..." : "Create a preview"}
              </button>

              <button
                type="button"
                onClick={removeFile}
                disabled={isBusy}
                style={{
                  background: "transparent",
                  border: "1px solid rgba(148, 163, 184, 0.3)",
                }}
              >
                Remove
              </button>
            </div>
          </div>
        )}

        {error && (
          <div
            style={{
              marginTop: 20,
              padding: 16,
              borderRadius: 12,
              border: "1px solid rgba(239, 68, 68, 0.35)",
              background: "rgba(239, 68, 68, 0.08)",
            }}
          >
            <strong>An error occurred.</strong>
            <p style={{ margin: "6px 0 0" }}>{error}</p>
          </div>
        )}
      </section>

      {preview && (
        <section className="panel pagePanel" style={{ marginTop: 20 }}>
          <div className="panelTop">
            <div>
              <p className="eyebrow">PREVIEW</p>
              <h2>Analysis result</h2>
              <p className="muted">
                Check the statistics before saving contacts to the database.
              </p>
            </div>
          </div>

          <div
            style={{
              marginTop: 24,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: 14,
            }}
          >
            <StatCard label="Found" value={preview.found} />
            <StatCard label="Valid" value={preview.valid} />
            <StatCard label="Invalid" value={preview.invalid} />
            <StatCard label="Duplicates" value={preview.duplicates} />
            <StatCard
              label="Ready for import"
              value={preview.ready_to_import}
            />
          </div>

          <div style={{ marginTop: 26 }}>
            <h3>Example of contacts</h3>

            {preview.preview.length > 0 ? (
              <div
                style={{
                  marginTop: 12,
                  border: "1px solid rgba(148, 163, 184, 0.2)",
                  borderRadius: 14,
                  overflow: "hidden",
                }}
              >
                {preview.preview.map((email, index) => (
                  <div
                    key={`${email}-${index}`}
                    style={{
                      padding: "12px 16px",
                      borderBottom:
                        index < preview.preview.length - 1
                          ? "1px solid rgba(148, 163, 184, 0.14)"
                          : "none",
                    }}
                  >
                    {email}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted" style={{ marginTop: 12 }}>
               No valid emails were found in the file.
              </p>
            )}
          </div>

          <div
            style={{
              marginTop: 24,
              display: "flex",
              justifyContent: "flex-end",
            }}
          >
            <button
              type="button"
              onClick={commitImport}
              disabled={
                isBusy ||
                preview.ready_to_import === 0 ||
                result !== null
              }
            >
              {isImporting
                ? "Importing contacts..."
                : `Import ${preview.ready_to_import} contacts`}
            </button>
          </div>
        </section>
      )}

      {result && (
        <section className="panel pagePanel" style={{ marginTop: 20 }}>
          <div
            style={{
              padding: 18,
              borderRadius: 14,
              border: "1px solid rgba(34, 197, 94, 0.35)",
              background: "rgba(34, 197, 94, 0.08)",
            }}
          >
            <p className="eyebrow">IMPORT COMPLETED</p>
            <h2 style={{ marginTop: 6 }}>Contacts have been processed</h2>
            <p className="muted">
              New contacts are stored in the email_targets table.
            </p>
          </div>

          <div
            style={{
              marginTop: 20,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
              gap: 14,
            }}
          >
            <StatCard label="New ones added" value={result.inserted} />
            <StatCard
              label="Already existed"
              value={result.already_existed}
            />
            <StatCard
              label="Duplicates in the file"
              value={result.duplicates_in_file}
            />
            <StatCard label="Invalid" value={result.invalid} />
          </div>

          <div
            style={{
              marginTop: 24,
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
            }}
          >
            <a
              href="/contacts"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "10px 16px",
                borderRadius: 10,
                textDecoration: "none",
                background: "var(--accent, #6366f1)",
                color: "#ffffff",
                fontWeight: 600,
              }}
            >
              Open contacts
            </a>

            <button type="button" onClick={removeFile}>
             Import a new file
            </button>
          </div>
        </section>
      )}
    </>
  );
}

type StatCardProps = {
  label: string;
  value: number;
};

function StatCard({ label, value }: StatCardProps) {
  return (
    <div
      style={{
        padding: 16,
        borderRadius: 14,
        border: "1px solid rgba(148, 163, 184, 0.2)",
        background: "rgba(148, 163, 184, 0.04)",
      }}
    >
      <p className="muted" style={{ margin: 0 }}>
        {label}
      </p>
      <strong
        style={{
          display: "block",
          marginTop: 8,
          fontSize: 26,
          lineHeight: 1,
        }}
      >
        {value}
      </strong>
    </div>
  );
}