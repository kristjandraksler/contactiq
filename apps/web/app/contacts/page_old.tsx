"use client";

import {
  ChangeEvent,
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

type Contact = {
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

type Pagination = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_previous: boolean;
  has_next: boolean;
};

type ContactsResponse = {
  items: Contact[];
  pagination: Pagination;
  filters: {
    search: string | null;
    status: string | null;
  };
};

type FinderResult = {
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

type EnrichmentResponse = {
  success: boolean;
  skipped: boolean;
  contact: Contact;
  result: FinderResult;
};

type BulkEnrichmentResponse = {
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

type Notice = {
  type: "success" | "error" | "info";
  title: string;
  message: string;
};

type BulkProgress = {
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

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

const PAGE_SIZE = 25;
const BULK_LIMIT = 10;
const MAX_SELECTED = 25;
const MAX_PAGES = 10;

const initialBulkProgress: BulkProgress = {
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

const statusOptions = [
  { value: "", label: "Vsi statusi" },
  { value: "NEW", label: "Čaka" },
  { value: "MATCHED", label: "Najdeno" },
  {
    value: "PARTIAL_MATCH",
    label: "Delno ujemanje",
  },
  { value: "NOT_FOUND", label: "Ni najdeno" },
  { value: "FAILED", label: "Napaka" },
];

function formatNumber(value: number): string {
  return new Intl.NumberFormat("sl-SI").format(value);
}

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat("sl-SI", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    NEW: "Čaka",
    MATCHED: "Najdeno",
    PARTIAL_MATCH: "Delno ujemanje",
    NOT_FOUND: "Ni najdeno",
    FAILED: "Napaka",
  };

  return labels[status] ?? status;
}

function getStatusClass(status: string): string {
  const classes: Record<string, string> = {
    NEW: "statusNew",
    MATCHED: "statusMatched",
    PARTIAL_MATCH: "statusPartial",
    NOT_FOUND: "statusNotFound",
    FAILED: "statusFailed",
  };

  return classes[status] ?? "";
}

function getPageNumbers(
  currentPage: number,
  totalPages: number,
): number[] {
  if (totalPages <= 5) {
    return Array.from(
      { length: totalPages },
      (_, index) => index + 1,
    );
  }

  let start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, start + 4);

  if (end - start < 4) {
    start = Math.max(1, end - 4);
  }

  return Array.from(
    { length: end - start + 1 },
    (_, index) => start + index,
  );
}

async function readErrorMessage(
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

export default function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);

  const [pagination, setPagination] =
    useState<Pagination>({
      page: 1,
      page_size: PAGE_SIZE,
      total: 0,
      total_pages: 0,
      has_previous: false,
      has_next: false,
    });

  const [searchInput, setSearchInput] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const [loading, setLoading] = useState(true);
  const [bulkLoading, setBulkLoading] =
    useState(false);

  const [enrichingIds, setEnrichingIds] = useState<
    string[]
  >([]);

  const [selectedIds, setSelectedIds] = useState<
    string[]
  >([]);

  const [bulkProgress, setBulkProgress] =
    useState<BulkProgress>(initialBulkProgress);

  const [error, setError] = useState<string | null>(
    null,
  );

  const [notice, setNotice] =
    useState<Notice | null>(null);

  const loadContacts = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
      });

      if (activeSearch.trim()) {
        params.set("search", activeSearch.trim());
      }

      if (status) {
        params.set("status", status);
      }

      const response = await fetch(
        `${API_URL}/contacts?${params.toString()}`,
        {
          cache: "no-store",
        },
      );

      if (!response.ok) {
        throw new Error(
          await readErrorMessage(
            response,
            "Kontaktov ni bilo mogoče naložiti.",
          ),
        );
      }

      const data: ContactsResponse =
        await response.json();

      setContacts(data.items);
      setPagination(data.pagination);

      setSelectedIds((current) =>
        current.filter((id) =>
          data.items.some(
            (contact) => contact.id === id,
          ),
        ),
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Pri nalaganju kontaktov je prišlo do napake.",
      );
    } finally {
      setLoading(false);
    }
  }, [activeSearch, page, status]);

  useEffect(() => {
    void loadContacts();
  }, [loadContacts]);

  const selectableContacts = useMemo(
    () =>
      contacts.filter(
        (contact) => !contact.phone,
      ),
    [contacts],
  );

  const selectableIds = useMemo(
    () =>
      selectableContacts.map(
        (contact) => contact.id,
      ),
    [selectableContacts],
  );

  const allSelectableSelected =
    selectableIds.length > 0 &&
    selectableIds.every((id) =>
      selectedIds.includes(id),
    );

  const someSelectableSelected =
    selectableIds.some((id) =>
      selectedIds.includes(id),
    ) && !allSelectableSelected;

  const progressPercentage =
    bulkProgress.total > 0
      ? Math.round(
          (bulkProgress.processed /
            bulkProgress.total) *
            100,
        )
      : 0;

  function handleSearch(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setNotice(null);
    setSelectedIds([]);
    setPage(1);
    setActiveSearch(searchInput);
  }

  function clearFilters() {
    setSearchInput("");
    setActiveSearch("");
    setStatus("");
    setPage(1);
    setNotice(null);
    setSelectedIds([]);
  }

  function handleStatusChange(
    event: ChangeEvent<HTMLSelectElement>,
  ) {
    setStatus(event.target.value);
    setPage(1);
    setNotice(null);
    setSelectedIds([]);
  }

  function toggleContactSelection(
    contactId: string,
  ) {
    if (bulkLoading) {
      return;
    }

    setNotice(null);

    setSelectedIds((current) => {
      if (current.includes(contactId)) {
        return current.filter(
          (id) => id !== contactId,
        );
      }

      if (current.length >= MAX_SELECTED) {
        setNotice({
          type: "info",
          title: "Dosežena je omejitev izbora.",
          message:
            `Naenkrat lahko izbereš največ ${MAX_SELECTED} kontaktov.`,
        });

        return current;
      }

      return [...current, contactId];
    });
  }

  function toggleAllOnPage() {
    if (bulkLoading) {
      return;
    }

    setNotice(null);

    if (allSelectableSelected) {
      setSelectedIds((current) =>
        current.filter(
          (id) => !selectableIds.includes(id),
        ),
      );

      return;
    }

    const currentOutsidePage = selectedIds.filter(
      (id) => !selectableIds.includes(id),
    );

    const remainingCapacity =
      MAX_SELECTED - currentOutsidePage.length;

    const idsToAdd = selectableIds.slice(
      0,
      remainingCapacity,
    );

    setSelectedIds([
      ...currentOutsidePage,
      ...idsToAdd,
    ]);

    if (selectableIds.length > remainingCapacity) {
      setNotice({
        type: "info",
        title: "Izbranih je največ 25 kontaktov.",
        message:
          "Na trenutni strani je več kontaktov, zato je sistem izbral prvih 25.",
      });
    }
  }

  function updateContactInTable(
    updatedContact: Contact,
  ) {
    setContacts((current) =>
      current.map((contact) =>
        contact.id === updatedContact.id
          ? updatedContact
          : contact,
      ),
    );
  }

  function showBulkNotice(
    data: BulkEnrichmentResponse,
  ) {
    if (data.processed === 0) {
      setNotice({
        type: "info",
        title: "Ni kontaktov za obdelavo.",
        message:
          data.message ??
          "Ni ustreznih kontaktov za iskanje telefonskih številk.",
      });

      return;
    }

    setNotice({
      type:
        data.failed > 0
          ? "info"
          : "success",
      title: `Obdelanih kontaktov: ${data.processed}`,
      message: [
        `najdeno ${data.matched}`,
        `delno ${data.partial_match}`,
        `ni najdeno ${data.not_found}`,
        `preskočeno ${data.skipped}`,
        `napake ${data.failed}`,
      ].join(" · "),
    });
  }

  async function enrichContact(
    contact: Contact,
    showNotice = true,
  ): Promise<EnrichmentResponse> {
    const params = new URLSearchParams({
      max_pages: String(MAX_PAGES),
    });

    const response = await fetch(
      `${API_URL}/enrichment/contacts/${
        contact.id
      }?${params.toString()}`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      },
    );

    if (!response.ok) {
      throw new Error(
        await readErrorMessage(
          response,
          "Telefonske številke ni bilo mogoče poiskati.",
        ),
      );
    }

    const data: EnrichmentResponse =
      await response.json();

    updateContactInTable(data.contact);

    if (!showNotice) {
      return data;
    }

    setSelectedIds((current) =>
      current.filter(
        (id) => id !== contact.id,
      ),
    );

    if (data.success && data.contact.phone) {
      setNotice({
        type: "success",
        title: "Telefonska številka je najdena.",
        message: `${data.contact.email}: ${
          data.contact.phone
        }${
          data.contact.confidence !== null
            ? ` (${data.contact.confidence}% confidence)`
            : ""
        }`,
      });

      return data;
    }

    if (data.skipped) {
      setNotice({
        type: "info",
        title: "Kontakt je bil preskočen.",
        message:
          data.result.error ??
          "Kontakt uporablja javnega ponudnika e-pošte.",
      });

      return data;
    }

    if (data.result.status === "NOT_FOUND") {
      setNotice({
        type: "info",
        title: "Telefonska številka ni bila najdena.",
        message:
          "Sistem je pregledal dostopne strani, vendar ni našel veljavne številke.",
      });

      return data;
    }

    setNotice({
      type: "error",
      title: "Iskanje ni uspelo.",
      message:
        data.result.error ??
        "Pri iskanju je prišlo do napake.",
    });

    return data;
  }

  async function handleSingleEnrichment(
    contact: Contact,
  ) {
    if (
      enrichingIds.includes(contact.id) ||
      bulkLoading
    ) {
      return;
    }

    try {
      setNotice(null);

      setEnrichingIds((current) => [
        ...current,
        contact.id,
      ]);

      await enrichContact(contact, true);
    } catch (err) {
      setNotice({
        type: "error",
        title: "Iskanje ni uspelo.",
        message:
          err instanceof Error
            ? err.message
            : "Pri iskanju je prišlo do napake.",
      });
    } finally {
      setEnrichingIds((current) =>
        current.filter(
          (id) => id !== contact.id,
        ),
      );
    }
  }

  async function enrichSelectedContacts() {
    if (
      bulkLoading ||
      selectedIds.length === 0
    ) {
      return;
    }

    const contactsToProcess = selectedIds
      .map((id) =>
        contacts.find(
          (contact) => contact.id === id,
        ),
      )
      .filter(
        (contact): contact is Contact =>
          Boolean(contact),
      );

    if (contactsToProcess.length === 0) {
      return;
    }

    setBulkLoading(true);
    setNotice(null);
    setEnrichingIds([]);

    setBulkProgress({
      ...initialBulkProgress,
      active: true,
      total: contactsToProcess.length,
    });

    let matched = 0;
    let partialMatch = 0;
    let notFound = 0;
    let skipped = 0;
    let failed = 0;

    for (const contact of contactsToProcess) {
      setEnrichingIds([contact.id]);

      setBulkProgress((current) => ({
        ...current,
        currentEmail: contact.email,
      }));

      try {
        const data = await enrichContact(
          contact,
          false,
        );

        const resultStatus = data.result.status;

        if (resultStatus === "MATCHED") {
          matched += 1;
        } else if (
          resultStatus === "PARTIAL_MATCH"
        ) {
          partialMatch += 1;
        } else if (
          resultStatus === "SKIPPED_FREE_EMAIL"
        ) {
          skipped += 1;
        } else if (
          resultStatus === "NOT_FOUND"
        ) {
          notFound += 1;
        } else {
          failed += 1;
        }
      } catch {
        failed += 1;
      }

      setBulkProgress((current) => ({
        ...current,
        processed: current.processed + 1,
        matched,
        partialMatch,
        notFound,
        skipped,
        failed,
      }));
    }

    setEnrichingIds([]);
    setSelectedIds([]);

    setBulkProgress((current) => ({
      ...current,
      active: false,
      currentEmail: null,
    }));

    setNotice({
      type:
        failed > 0
          ? "info"
          : "success",
      title: `Obdelanih kontaktov: ${contactsToProcess.length}`,
      message: [
        `najdeno ${matched}`,
        `delno ${partialMatch}`,
        `ni najdeno ${notFound}`,
        `preskočeno ${skipped}`,
        `napake ${failed}`,
      ].join(" · "),
    });

    setBulkLoading(false);
  }

  async function bulkEnrichContacts() {
    if (bulkLoading) {
      return;
    }

    try {
      setBulkLoading(true);
      setNotice(null);

      const params = new URLSearchParams({
        limit: String(BULK_LIMIT),
        max_pages: String(MAX_PAGES),
        retry_failed: "false",
      });

      const response = await fetch(
        `${API_URL}/enrichment/bulk?${params.toString()}`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
          },
        },
      );

      if (!response.ok) {
        throw new Error(
          await readErrorMessage(
            response,
            "Množične obdelave ni bilo mogoče izvesti.",
          ),
        );
      }

      const data: BulkEnrichmentResponse =
        await response.json();

      await loadContacts();
      showBulkNotice(data);
    } catch (err) {
      setNotice({
        type: "error",
        title: "Množična obdelava ni uspela.",
        message:
          err instanceof Error
            ? err.message
            : "Pri množični obdelavi je prišlo do napake.",
      });
    } finally {
      setBulkLoading(false);
    }
  }

  const pageNumbers = getPageNumbers(
    pagination.page,
    pagination.total_pages,
  );

  const resultStart =
    pagination.total === 0
      ? 0
      : (pagination.page - 1) *
          pagination.page_size +
        1;

  const resultEnd = Math.min(
    pagination.page * pagination.page_size,
    pagination.total,
  );

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">KONTAKTI</p>
          <h1>Kontakti</h1>
          <p className="muted">
            Pregled e-mailov, telefonov in kakovosti
            ujemanja.
          </p>
        </div>

        <div
          style={{
            display: "flex",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          <button
            type="button"
            onClick={() =>
              void bulkEnrichContacts()
            }
            disabled={
              loading ||
              bulkLoading ||
              enrichingIds.length > 0
            }
          >
            {bulkLoading
              ? "Obdelujem kontakte …"
              : `Obdelaj naslednjih ${BULK_LIMIT}`}
          </button>

          <button
            type="button"
            className="secondaryButton"
            onClick={() => void loadContacts()}
            disabled={loading || bulkLoading}
          >
            {loading
              ? "Osvežujem …"
              : "Osveži podatke"}
          </button>
        </div>
      </header>

      {notice && (
        <div
          className={`alert ${
            notice.type === "error"
              ? "alertError"
              : ""
          }`}
          style={{
            marginBottom: "20px",
          }}
        >
          <div>
            <strong>{notice.title}</strong>
            <p>{notice.message}</p>
          </div>

          <button
            type="button"
            className="smallButton"
            onClick={() => setNotice(null)}
          >
            Zapri
          </button>
        </div>
      )}

      <section className="panel pagePanel">
        <div className="panelTop contactsPanelTop">
          <div>
            <h2>Seznam kontaktov</h2>
            <p className="muted">
              Skupaj{" "}
              {formatNumber(pagination.total)} kontaktov.
            </p>
          </div>

          <form
            className="filters"
            onSubmit={handleSearch}
          >
            <input
              type="search"
              value={searchInput}
              onChange={(event) =>
                setSearchInput(event.target.value)
              }
              placeholder="Išči po e-mailu ali domeni"
              aria-label="Išči kontakte"
            />

            <select
              value={status}
              onChange={handleStatusChange}
              aria-label="Filtriraj po statusu"
            >
              {statusOptions.map((option) => (
                <option
                  key={option.value || "all"}
                  value={option.value}
                >
                  {option.label}
                </option>
              ))}
            </select>

            <button
              type="submit"
              disabled={loading || bulkLoading}
            >
              Išči
            </button>

            {(activeSearch || status) && (
              <button
                type="button"
                className="ghostButton"
                onClick={clearFilters}
              >
                Počisti
              </button>
            )}
          </form>
        </div>

        {selectedIds.length > 0 && (
          <div
            className="alert"
            style={{
              margin: "0 0 18px",
              alignItems: "center",
            }}
          >
            <div>
              <strong>
                Izbranih kontaktov:{" "}
                {selectedIds.length}
              </strong>
              <p>
                Naenkrat lahko obdelaš največ{" "}
                {MAX_SELECTED} kontaktov.
              </p>
            </div>

            <div
              style={{
                display: "flex",
                gap: "10px",
                flexWrap: "wrap",
              }}
            >
              <button
                type="button"
                onClick={() =>
                  void enrichSelectedContacts()
                }
                disabled={bulkLoading}
              >
                {bulkLoading
                  ? "Iščem telefonske številke …"
                  : "Poišči telefone za izbrane"}
              </button>

              <button
                type="button"
                className="ghostButton"
                onClick={() => setSelectedIds([])}
                disabled={bulkLoading}
              >
                Počisti izbor
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="alert alertError panelAlert">
            <div>
              <strong>
                Kontaktov ni bilo mogoče prikazati.
              </strong>
              <p>{error}</p>
            </div>

            <button
              type="button"
              className="smallButton"
              onClick={() => void loadContacts()}
            >
              Poskusi znova
            </button>
          </div>
        )}

        {loading ? (
          <div className="stateMessage largeState">
            <div className="spinner" />
            <p>Nalaganje kontaktov …</p>
          </div>
        ) : contacts.length === 0 ? (
          <div className="stateMessage largeState">
            <h3>Ni rezultatov</h3>
            <p>
              Za izbrane filtre ni bilo mogoče najti
              kontaktov.
            </p>

            {(activeSearch || status) && (
              <button
                type="button"
                className="secondaryButton"
                onClick={clearFilters}
              >
                Počisti filtre
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="tableWrapper">
              <table>
                <thead>
                  <tr>
                    <th
                      style={{
                        width: "42px",
                        textAlign: "center",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={
                          allSelectableSelected
                        }
                        ref={(element) => {
                          if (element) {
                            element.indeterminate =
                              someSelectableSelected;
                          }
                        }}
                        onChange={toggleAllOnPage}
                        disabled={
                          bulkLoading ||
                          selectableIds.length === 0
                        }
                        aria-label="Izberi vse kontakte na strani"
                      />
                    </th>

                    <th>E-mail</th>
                    <th>Domena</th>
                    <th>Telefon</th>
                    <th>Status</th>
                    <th>Confidence</th>
                    <th>Poskusi</th>
                    <th>Zadnja obdelava</th>
                    <th>Akcija</th>
                  </tr>
                </thead>

                <tbody>
                  {contacts.map((contact) => {
                    const isEnriching =
                      enrichingIds.includes(
                        contact.id,
                      );

                    const hasPhone =
                      Boolean(contact.phone);

                    const isSelected =
                      selectedIds.includes(
                        contact.id,
                      );

                    return (
                      <tr key={contact.id}>
                        <td
                          style={{
                            textAlign: "center",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={
                              hasPhone ||
                              bulkLoading ||
                              isEnriching
                            }
                            onChange={() =>
                              toggleContactSelection(
                                contact.id,
                              )
                            }
                            aria-label={`Izberi ${contact.email}`}
                          />
                        </td>

                        <td>
                          <strong className="emailCell">
                            {contact.email}
                          </strong>
                        </td>

                        <td>
                          {contact.website ? (
                            <a
                              href={contact.website}
                              target="_blank"
                              rel="noreferrer"
                              className="tableLink"
                            >
                              {contact.domain}
                            </a>
                          ) : (
                            contact.domain
                          )}
                        </td>

                        <td>
                          {contact.phone ? (
                            <a
                              href={`tel:${contact.phone}`}
                              className="tableLink"
                            >
                              {contact.phone}
                            </a>
                          ) : (
                            "—"
                          )}
                        </td>

                        <td>
                          <span
                            className={`statusBadge ${getStatusClass(
                              contact.status,
                            )}`}
                          >
                            {isEnriching
                              ? "Obdelujem"
                              : getStatusLabel(
                                  contact.status,
                                )}
                          </span>
                        </td>

                        <td>
                          {contact.confidence !== null
                            ? `${contact.confidence}%`
                            : "—"}
                        </td>

                        <td>
                          {contact.scan_attempts}
                        </td>

                        <td>
                          {formatDate(
                            contact.last_scan,
                          )}
                        </td>

                        <td>
                          <button
                            type="button"
                            className={
                              hasPhone
                                ? "ghostButton"
                                : "smallButton"
                            }
                            disabled={
                              isEnriching ||
                              bulkLoading
                            }
                            onClick={() =>
                              void handleSingleEnrichment(
                                contact,
                              )
                            }
                          >
                            {isEnriching
                              ? "Iščem …"
                              : hasPhone
                                ? "Poišči znova"
                                : "Poišči telefon"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="paginationBar">
              <p className="paginationInfo">
                Prikazujem{" "}
                <strong>
                  {formatNumber(resultStart)}–
                  {formatNumber(resultEnd)}
                </strong>{" "}
                od{" "}
                <strong>
                  {formatNumber(
                    pagination.total,
                  )}
                </strong>
              </p>

              <div className="paginationControls">
                <button
                  type="button"
                  className="paginationButton"
                  disabled={
                    !pagination.has_previous ||
                    loading ||
                    bulkLoading
                  }
                  onClick={() => {
                    setSelectedIds([]);
                    setPage((current) =>
                      Math.max(1, current - 1),
                    );
                  }}
                >
                  Prejšnja
                </button>

                <div className="pageNumbers">
                  {pageNumbers.map(
                    (pageNumber) => (
                      <button
                        type="button"
                        key={pageNumber}
                        className={`pageButton ${
                          pageNumber ===
                          pagination.page
                            ? "pageButtonActive"
                            : ""
                        }`}
                        onClick={() => {
                          setSelectedIds([]);
                          setPage(pageNumber);
                        }}
                        disabled={
                          loading ||
                          bulkLoading
                        }
                      >
                        {pageNumber}
                      </button>
                    ),
                  )}
                </div>

                <button
                  type="button"
                  className="paginationButton"
                  disabled={
                    !pagination.has_next ||
                    loading ||
                    bulkLoading
                  }
                  onClick={() => {
                    setSelectedIds([]);
                    setPage(
                      (current) =>
                        current + 1,
                    );
                  }}
                >
                  Naslednja
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      {bulkProgress.total > 0 && (
        <>
          <div
            onClick={() => {
              if (!bulkProgress.active) {
                setBulkProgress(initialBulkProgress);
              }
            }}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 999,
              background: "rgba(0, 0, 0, 0.42)",
              backdropFilter: "blur(2px)",
              opacity: bulkProgress.active ? 0.7 : 1,
              pointerEvents: bulkProgress.active ? "none" : "auto",
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
              borderLeft: "1px solid rgba(255, 255, 255, 0.1)",
              background:
                "linear-gradient(180deg, rgba(23, 18, 38, 0.98), rgba(12, 10, 22, 0.99))",
              boxShadow: "-24px 0 70px rgba(0, 0, 0, 0.45)",
              display: "flex",
              flexDirection: "column",
              gap: "24px",
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
                <p className="eyebrow">ENRICHMENT JOB</p>
                <h2 style={{ margin: "6px 0 8px" }}>
                  {bulkProgress.active
                    ? "Iskanje telefonskih številk"
                    : "Iskanje je končano"}
                </h2>
                <p className="muted" style={{ margin: 0 }}>
                  {bulkProgress.active
                    ? "Rezultati se sproti zapisujejo med kontakte."
                    : `Obdelanih je bilo ${bulkProgress.processed} kontaktov.`}
                </p>
              </div>

              {!bulkProgress.active && (
                <button
                  type="button"
                  className="ghostButton"
                  onClick={() =>
                    setBulkProgress(initialBulkProgress)
                  }
                  aria-label="Zapri panel"
                  style={{
                    minWidth: "42px",
                    width: "42px",
                    height: "42px",
                    padding: 0,
                    fontSize: "22px",
                    lineHeight: 1,
                  }}
                >
                  ×
                </button>
              )}
            </div>

            <div
              style={{
                padding: "20px",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "18px",
                background: "rgba(255, 255, 255, 0.045)",
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
                <strong style={{ fontSize: "32px" }}>
                  {progressPercentage}%
                </strong>

                <span className="muted">
                  {bulkProgress.processed} / {bulkProgress.total}
                </span>
              </div>

              <div
                style={{
                  width: "100%",
                  height: "12px",
                  overflow: "hidden",
                  borderRadius: "999px",
                  background: "rgba(255, 255, 255, 0.08)",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${progressPercentage}%`,
                    borderRadius: "999px",
                    background:
                      "linear-gradient(90deg, #7c3aed, #a855f7)",
                    transition: "width 300ms ease",
                  }}
                />
              </div>
            </div>

            {bulkProgress.active &&
              bulkProgress.currentEmail && (
                <div
                  style={{
                    padding: "18px",
                    borderRadius: "16px",
                    border:
                      "1px solid rgba(168, 85, 247, 0.28)",
                    background: "rgba(168, 85, 247, 0.08)",
                  }}
                >
                  <span
                    className="muted"
                    style={{
                      display: "block",
                      marginBottom: "7px",
                      fontSize: "13px",
                    }}
                  >
                    TRENUTNO OBDELUJEM
                  </span>

                  <strong
                    style={{
                      display: "block",
                      wordBreak: "break-word",
                    }}
                  >
                    {bulkProgress.currentEmail}
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
                  value: bulkProgress.matched,
                  symbol: "✓",
                },
                {
                  label: "Delno",
                  value: bulkProgress.partialMatch,
                  symbol: "~",
                },
                {
                  label: "Ni najdeno",
                  value: bulkProgress.notFound,
                  symbol: "×",
                },
                {
                  label: "Preskočeno",
                  value: bulkProgress.skipped,
                  symbol: "↷",
                },
                {
                  label: "Napake",
                  value: bulkProgress.failed,
                  symbol: "!",
                },
                {
                  label: "Obdelano",
                  value: bulkProgress.processed,
                  symbol: "#",
                },
              ].map((item) => (
                <div
                  key={item.label}
                  style={{
                    padding: "16px",
                    borderRadius: "15px",
                    border:
                      "1px solid rgba(255, 255, 255, 0.08)",
                    background: "rgba(255, 255, 255, 0.035)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: "10px",
                      marginBottom: "9px",
                    }}
                  >
                    <span className="muted">
                      {item.label}
                    </span>

                    <span
                      aria-hidden="true"
                      style={{
                        opacity: 0.72,
                        fontWeight: 700,
                      }}
                    >
                      {item.symbol}
                    </span>
                  </div>

                  <strong style={{ fontSize: "24px" }}>
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
              {bulkProgress.active ? (
                <p
                  className="muted"
                  style={{
                    margin: 0,
                    textAlign: "center",
                    fontSize: "13px",
                  }}
                >
                  Panel se zapre šele, ko je obdelava končana.
                </p>
              ) : (
                <button
                  type="button"
                  onClick={() =>
                    setBulkProgress(initialBulkProgress)
                  }
                  style={{ width: "100%" }}
                >
                  Zapri
                </button>
              )}
            </div>
          </aside>
        </>
      )}

    </>
  );
}