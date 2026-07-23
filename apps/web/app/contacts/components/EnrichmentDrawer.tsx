"use client";

import type { BulkProgress } from "../types";

type EnrichmentDrawerProps = {
  progress: BulkProgress;
  percentage: number;
  onClose: () => void;
};

export default function EnrichmentDrawer({
  progress,
  percentage,
  onClose,
}: EnrichmentDrawerProps) {
  if (progress.total <= 0) return null;

  return (
    <>
      <div
        onClick={() => {
          if (!progress.active) onClose();
        }}
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 999,
          background: "rgba(0, 0, 0, 0.42)",
          backdropFilter: "blur(2px)",
          opacity: progress.active ? 0.7 : 1,
          pointerEvents: progress.active
            ? "none"
            : "auto",
        }}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Napredek masovnega iskanja"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          zIndex: 1000,
          width: "min(420px, 100vw)",
          height: "100vh",
          padding: "28px",
          overflowY: "auto",
          borderLeft:
            "1px solid rgba(255, 255, 255, 0.1)",
          background:
            "linear-gradient(180deg, rgba(23, 18, 38, 0.98), rgba(12, 10, 22, 0.99))",
          boxShadow:
            "-24px 0 70px rgba(0, 0, 0, 0.45)",
          display: "flex",
          flexDirection: "column",
          gap: "24px",
          color: "#ffffff",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: "16px",
          }}
        >
          <div>
            <p className="eyebrow">
              ENRICHMENT JOB
            </p>

            <h2
              style={{
                margin: "6px 0 8px",
                color: "#ffffff",
              }}
            >
              {progress.active
                ? "Iskanje telefonskih številk"
                : "Iskanje je končano"}
            </h2>

            <p
              className="muted"
              style={{
                margin: 0,
              }}
            >
              {progress.active
                ? "Rezultati se sproti zapisujejo med kontakte."
                : `Obdelanih je bilo ${progress.processed} kontaktov.`}
            </p>
          </div>

          {!progress.active && (
            <button
              type="button"
              className="ghostButton"
              onClick={onClose}
              aria-label="Zapri panel"
              style={{
                minWidth: "42px",
                width: "42px",
                height: "42px",
                padding: 0,
                fontSize: "22px",
                lineHeight: 1,
                color: "#ffffff",
              }}
            >
              ×
            </button>
          )}
        </div>

        <div
          style={{
            padding: "20px",
            border:
              "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "18px",
            background:
              "rgba(255, 255, 255, 0.045)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              gap: "16px",
              marginBottom: "14px",
            }}
          >
            <strong
              style={{
                fontSize: "32px",
                color: "#ffffff",
              }}
            >
              {percentage}%
            </strong>

            <span
              style={{
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "16px",
              }}
            >
              {progress.processed} /{" "}
              {progress.total}
            </span>
          </div>

          <div
            style={{
              width: "100%",
              height: "12px",
              overflow: "hidden",
              borderRadius: "999px",
              background:
                "rgba(255, 255, 255, 0.12)",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${percentage}%`,
                borderRadius: "999px",
                background:
                  "linear-gradient(90deg, #7c3aed, #a855f7)",
                transition: "width 300ms ease",
              }}
            />
          </div>
        </div>

        {progress.active &&
          progress.currentEmail && (
            <div
              style={{
                padding: "18px",
                borderRadius: "16px",
                border:
                  "1px solid rgba(168, 85, 247, 0.38)",
                background:
                  "rgba(168, 85, 247, 0.11)",
              }}
            >
              <span
                style={{
                  display: "block",
                  marginBottom: "7px",
                  fontSize: "13px",
                  color:
                    "rgba(255, 255, 255, 0.72)",
                }}
              >
                TRENUTNO OBDELUJEM
              </span>

              <strong
                style={{
                  display: "block",
                  wordBreak: "break-word",
                  color: "#ffffff",
                  fontSize: "16px",
                }}
              >
                {progress.currentEmail}
              </strong>
            </div>
          )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "12px",
          }}
        >
          {[
            {
              label: "Najdeno",
              value: progress.matched,
              symbol: "✓",
            },
            {
              label: "Delno",
              value: progress.partialMatch,
              symbol: "~",
            },
            {
              label: "Ni najdeno",
              value: progress.notFound,
              symbol: "×",
            },
            {
              label: "Preskočeno",
              value: progress.skipped,
              symbol: "↷",
            },
            {
              label: "Napake",
              value: progress.failed,
              symbol: "!",
            },
            {
              label: "Obdelano",
              value: progress.processed,
              symbol: "#",
            },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                padding: "16px",
                borderRadius: "15px",
                border:
                  "1px solid rgba(255, 255, 255, 0.1)",
                background:
                  "rgba(255, 255, 255, 0.045)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent:
                    "space-between",
                  alignItems: "center",
                  gap: "10px",
                  marginBottom: "9px",
                }}
              >
                <span
                  style={{
                    color:
                      "rgba(255, 255, 255, 0.68)",
                  }}
                >
                  {item.label}
                </span>

                <span
                  aria-hidden="true"
                  style={{
                    color: "#ffffff",
                    opacity: 0.9,
                    fontWeight: 700,
                  }}
                >
                  {item.symbol}
                </span>
              </div>

              <strong
                style={{
                  fontSize: "24px",
                  color: "#ffffff",
                }}
              >
                {item.value}
              </strong>
            </div>
          ))}
        </div>

        <div
          style={{
            marginTop: "auto",
            paddingTop: "12px",
          }}
        >
          {progress.active ? (
            <p
              style={{
                margin: 0,
                textAlign: "center",
                fontSize: "13px",
                color:
                  "rgba(255, 255, 255, 0.65)",
              }}
            >
              Panel se zapre šele, ko je obdelava
              končana.
            </p>
          ) : (
            <button
              type="button"
              onClick={onClose}
              style={{
                width: "100%",
              }}
            >
              Zapri
            </button>
          )}
        </div>
      </aside>
    </>
  );
}