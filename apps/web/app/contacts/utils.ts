export function formatNumber(value: number): string {
  return new Intl.NumberFormat("sl-SI").format(value);
}

export function formatDate(value: string | null): string {
  if (!value) return "—";

  return new Intl.DateTimeFormat("sl-SI", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    NEW: "Čaka",
    MATCHED: "Najdeno",
    PARTIAL_MATCH: "Delno ujemanje",
    NOT_FOUND: "Ni najdeno",
    FAILED: "Napaka",
  };

  return labels[status] ?? status;
}

export function getStatusClass(status: string): string {
  const classes: Record<string, string> = {
    NEW: "statusNew",
    MATCHED: "statusMatched",
    PARTIAL_MATCH: "statusPartial",
    NOT_FOUND: "statusNotFound",
    FAILED: "statusFailed",
  };

  return classes[status] ?? "";
}

export function getPageNumbers(
  currentPage: number,
  totalPages: number,
): number[] {
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  let start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, start + 4);

  if (end - start < 4) start = Math.max(1, end - 4);

  return Array.from(
    { length: end - start + 1 },
    (_, index) => start + index,
  );
}

export async function readErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  const body = await response.json().catch(() => null);

  if (
    body &&
    typeof body === "object" &&
    typeof body.detail === "string"
  ) {
    return body.detail;
  }

  return fallback;
}
