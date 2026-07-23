import type { BulkProgress } from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

export const DEFAULT_PAGE_SIZE = 25;

export const PAGE_SIZE_OPTIONS = [
  25,
  50,
  100,
  250,
] as const;

export const BULK_LIMIT = 10;
export const MAX_SELECTED = 250;
export const MAX_PAGES = 10;

export const initialBulkProgress: BulkProgress = {
  active: false,
  total: 0,
  processed: 0,
  matched: 0,
  partialMatch: 0,
  notFound: 0,
  skipped: 0,
  failed: 0,
  currentEmail: null,
};

export const statusOptions = [
  { value: "", label: "Vsi statusi" },
  { value: "NEW", label: "Čaka" },
  { value: "MATCHED", label: "Najdeno" },
  { value: "PARTIAL_MATCH", label: "Delno ujemanje" },
  { value: "NOT_FOUND", label: "Ni najdeno" },
  { value: "FAILED", label: "Napaka" },
];