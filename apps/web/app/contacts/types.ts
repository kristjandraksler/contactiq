export type Contact = {
  id: string;
  email: string;
  domain: string;
  website: string | null;
  phone: string | null;
  confidence: number | null;
  source_url: string | null;
  pages_scanned: number;
  scan_attempts: number;
  scan_duration_ms: number | null;
  last_scan: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Pagination = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_previous: boolean;
  has_next: boolean;
};

export type ContactsResponse = {
  items: Contact[];
  pagination: Pagination;
  filters: {
    search: string | null;
    status: string | null;
  };
};

export type FinderResult = {
  status: string;
  website?: string | null;
  phone?: string | null;
  confidence?: number | null;
  source_url?: string | null;
  pages_scanned?: number;
  scan_duration_ms?: number;
  candidates?: Array<{
    phone: string;
    score: number;
    source_url: string;
    occurrences: number;
    from_tel_link: boolean;
  }>;
  error: string | null;
};

export type EnrichmentResponse = {
  success: boolean;
  skipped: boolean;
  contact: Contact;
  result: FinderResult;
};

export type BulkEnrichmentResponse = {
  status: string;
  requested?: number;
  requested_limit?: number;
  processed: number;
  missing?: number;
  missing_ids?: string[];
  matched: number;
  partial_match: number;
  not_found: number;
  skipped: number;
  failed: number;
  items: EnrichmentResponse[];
  message?: string;
};

export type Notice = {
  type: "success" | "error" | "info";
  title: string;
  message: string;
};

export type BulkProgress = {
  active: boolean;
  total: number;
  processed: number;
  matched: number;
  partialMatch: number;
  notFound: number;
  skipped: number;
  failed: number;
  currentEmail: string | null;
};
