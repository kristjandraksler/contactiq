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

const PUBLIC_EMAIL_DOMAINS = new Set([
  "gmail.com",
  "googlemail.com",
  "outlook.com",
  "hotmail.com",
  "live.com",
  "msn.com",
  "yahoo.com",
  "yahoo.co.uk",
  "icloud.com",
  "me.com",
  "mac.com",
  "aol.com",
  "proton.me",
  "protonmail.com",
  "gmx.com",
  "gmx.net",
  "mail.com",
  "zoho.com",
  "telemach.net",
  "siol.net",
]);

export function isPublicEmailDomain(domain: string): boolean {
  return PUBLIC_EMAIL_DOMAINS.has(domain.trim().toLowerCase());
}

export function getDisplayStatus(
  status: string,
  phone?: string | null,
  domain?: string,
): string {
  if (phone) return "MATCHED";

  if (
    status === "PARTIAL_MATCH" ||
    status === "NOT_FOUND" ||
    status === "EMAIL_FOUND" ||
    status === "SKIPPED_FREE_EMAIL" ||
    (status === "FAILED" && domain && isPublicEmailDomain(domain))
  ) {
    return "NO_PHONE";
  }

  return status;
}

export function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    NEW: "Čaka",
    MATCHED: "Telefon najden",
    NO_PHONE: "Brez telefona",
    PARTIAL_MATCH: "Brez telefona",
    NOT_FOUND: "Brez telefona",
    EMAIL_FOUND: "Brez telefona",
    SKIPPED_FREE_EMAIL: "Brez telefona",
    FAILED: "Napaka",
  };

  return labels[status] ?? status;
}

export function getStatusClass(status: string): string {
  const classes: Record<string, string> = {
    NEW: "statusNew",
    MATCHED: "statusMatched",
    NO_PHONE: "statusNotFound",
    PARTIAL_MATCH: "statusNotFound",
    NOT_FOUND: "statusNotFound",
    EMAIL_FOUND: "statusNotFound",
    SKIPPED_FREE_EMAIL: "statusNotFound",
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
