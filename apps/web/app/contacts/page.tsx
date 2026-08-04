"use client";

import "./ui-v3.css";

import {
  ChangeEvent,
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import EnrichmentDrawer from "./components/EnrichmentDrawer";
import {
  API_URL,
  DEFAULT_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
  initialBulkProgress,
  MAX_PAGES,
  MAX_SELECTED,
  statusOptions,
} from "./constants";
import type {
  BulkEnrichmentResponse,
  BulkProgress,
  Contact,
  ContactsResponse,
  EnrichmentResponse,
  Notice,
  Pagination,
} from "./types";
import {
  formatDate,
  formatNumber,
  getDisplayStatus,
  getPageNumbers,
  getStatusClass,
  getStatusLabel,
  readErrorMessage,
} from "./utils";

type CountryOption = {
  code: string;
  name: string | null;
  flag: string | null;
  count: number;
};

type GeoContact = Contact & {
  country_code?: string | null;
  country_name?: string | null;
  country_flag?: string | null;
  country_confidence?: number | null;
  country_source?: string | null;
  country_evidence?: string[] | null;
  person_match_type?: string | null;
  phone_country_code?: string | null;
  phone_country_name?: string | null;
  phone_country_flag?: string | null;
  phone_country_confidence?: number | null;
  country_mismatch?: boolean;
  is_cross_border?: boolean;
};


type CountryIntelligenceProps = {
  flag?: string | null;
  name?: string | null;
  code?: string | null;
  confidence?: number | null;
  source?: string | null;
  evidence?: string[] | null;
  compact?: boolean;
};

function getConfidenceMeta(value?: number | null) {
  const confidence = value ?? 0;

  if (confidence >= 90) {
    return {
      label: "VERY HIGH",
      dot: "🟢",
      background: "rgba(22, 163, 74, 0.12)",
      border: "rgba(22, 163, 74, 0.28)",
    };
  }

  if (confidence >= 75) {
    return {
      label: "HIGH",
      dot: "🟢",
      background: "rgba(34, 197, 94, 0.10)",
      border: "rgba(34, 197, 94, 0.24)",
    };
  }

  if (confidence >= 50) {
    return {
      label: "MEDIUM",
      dot: "🟡",
      background: "rgba(234, 179, 8, 0.12)",
      border: "rgba(234, 179, 8, 0.28)",
    };
  }

  return {
    label: "LOW",
    dot: "🔴",
    background: "rgba(239, 68, 68, 0.10)",
    border: "rgba(239, 68, 68, 0.24)",
  };
}

function formatEvidence(value: string) {
  const [kind, raw] = value.split(":", 2);

  const labels: Record<string, string> = {
    schema_address: "Schema.org naslov",
    og_locale: "OpenGraph locale",
    html_lang: "HTML jezik",
    hreflang: "Hreflang",
    page_text: "Besedilo strani",
    currency: "Valuta",
    tld: "Domena TLD",
    phone_fallback: "Telefonska država",
    phone: "Telefonska država",
  };

  return `${labels[kind] ?? kind}${raw ? ` · ${raw}` : ""}`;
}

function ConfidenceBadge({
  value,
}: {
  value?: number | null;
}) {
  if (value === null || value === undefined) {
    return <span className="muted">—</span>;
  }

  const meta = getConfidenceMeta(value);

  return (
    <span
      title={`${meta.label} confidence`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "5px 8px",
        borderRadius: "999px",
        background: meta.background,
        border: `1px solid ${meta.border}`,
        fontSize: "12px",
        fontWeight: 700,
        whiteSpace: "nowrap",
      }}
    >
      <span>{meta.dot}</span>
      <span>{meta.label}</span>
      <span>{value}%</span>
    </span>
  );
}

function CountryIntelligence({
  flag,
  name,
  code,
  confidence,
  source,
  evidence,
  compact = false,
}: CountryIntelligenceProps) {
  if (!code) {
    return <span className="muted">—</span>;
  }

  const evidenceItems = evidence ?? [];

  return (
    <details
      style={{
        display: "inline-block",
        position: "relative",
      }}
    >
      <summary
        title="Open Country Intelligence"
        style={{
          cursor: "pointer",
          listStyle: "none",
          display: "inline-flex",
          alignItems: "center",
          gap: "7px",
          padding: compact ? "4px 6px" : "6px 8px",
          borderRadius: "10px",
          border: "1px solid rgba(148, 163, 184, 0.22)",
          background: "rgba(148, 163, 184, 0.06)",
          whiteSpace: "nowrap",
        }}
      >
        <span>{flag ?? "🌍"}</span>
        <strong>{compact ? code : name ?? code}</strong>
        {confidence !== null && confidence !== undefined && (
          <span className="muted" style={{ fontSize: "12px" }}>
            {confidence}%
          </span>
        )}
      </summary>

      <div
        style={{
          position: "absolute",
          zIndex: 30,
          top: "calc(100% + 8px)",
          left: 0,
          width: "280px",
          padding: "14px",
          borderRadius: "14px",
          border: "1px solid rgba(148, 163, 184, 0.25)",
          background: "var(--panel, #ffffff)",
          boxShadow: "0 18px 50px rgba(15, 23, 42, 0.18)",
        }}
      >
        <p
          style={{
            margin: "0 0 10px",
            fontSize: "12px",
            fontWeight: 800,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          Country Intelligence
        </p>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "12px",
            marginBottom: "12px",
          }}
        >
          <div>
            <div style={{ fontSize: "20px", marginBottom: "4px" }}>
              {flag ?? "🌍"} {name ?? code}
            </div>
            <div className="muted" style={{ fontSize: "12px" }}>
              Vir: {source ?? "unknown"}
            </div>
          </div>

          <ConfidenceBadge value={confidence} />
        </div>

        <div
          style={{
            borderTop: "1px solid rgba(148, 163, 184, 0.18)",
            paddingTop: "10px",
          }}
        >
          <strong style={{ fontSize: "12px" }}>Evidence</strong>

          {evidenceItems.length > 0 ? (
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "6px",
                marginTop: "8px",
              }}
            >
              {evidenceItems.map((item) => (
                <span
                  key={item}
                  style={{
                    padding: "5px 7px",
                    borderRadius: "8px",
                    background: "rgba(34, 197, 94, 0.10)",
                    border: "1px solid rgba(34, 197, 94, 0.20)",
                    fontSize: "11px",
                  }}
                >
                  ✓ {formatEvidence(item)}
                </span>
              ))}
            </div>
          ) : (
            <p className="muted" style={{ margin: "6px 0 0" }}>
              The record has not yet been written.
            </p>
          )}
        </div>
      </div>
    </details>
  );
}

function MatchTypeBadge({
  type,
}: {
  type?: string | null;
}) {
  const map: Record<string, { label: string; icon: string }> = {
    person_phone: { label: "PERSON", icon: "👤" },
    company_phone: { label: "COMPANY", icon: "🏢" },
    public_person: { label: "PUBLIC PERSON", icon: "👤" },
    public_email: { label: "PUBLIC EMAIL", icon: "🟣" },
    role_phone: { label: "DEPARTMENT", icon: "📞" },
    none: { label: "NONE", icon: "—" },
  };

  const item = map[type ?? "none"] ?? {
    label: type?.toUpperCase() ?? "NONE",
    icon: "•",
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding: "4px 7px",
        borderRadius: "999px",
        background: "rgba(99, 102, 241, 0.08)",
        border: "1px solid rgba(99, 102, 241, 0.18)",
        fontSize: "11px",
        fontWeight: 700,
        whiteSpace: "nowrap",
      }}
    >
      {item.icon} {item.label}
    </span>
  );
}

function CrossBorderBadge() {
  return (
    <span
      title="The country of the company and the phone are different."
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding: "4px 7px",
        borderRadius: "999px",
        background: "rgba(245, 158, 11, 0.12)",
        border: "1px solid rgba(245, 158, 11, 0.28)",
        fontSize: "11px",
        fontWeight: 800,
        whiteSpace: "nowrap",
      }}
    >
      🌍 CROSS-BORDER
    </span>
  );
}

export default function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);

  const [pageSize, setPageSize] =
    useState(DEFAULT_PAGE_SIZE);

  const [pagination, setPagination] =
    useState<Pagination>({
      page: 1,
      page_size: DEFAULT_PAGE_SIZE,
      total: 0,
      total_pages: 0,
      has_previous: false,
      has_next: false,
    });

  const [searchInput, setSearchInput] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [status, setStatus] = useState("");
  const [companyCountry, setCompanyCountry] = useState("");
  const [phoneCountry, setPhoneCountry] = useState("");
  const [companyCountries, setCompanyCountries] = useState<CountryOption[]>([]);
  const [phoneCountries, setPhoneCountries] = useState<CountryOption[]>([]);
  const [mismatchOnly, setMismatchOnly] = useState(false);
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
        page_size: String(pageSize),
      });

      if (activeSearch.trim()) {
        params.set("search", activeSearch.trim());
      }

      if (status) {
        params.set("status", status);
      }

      if (companyCountry) {
        params.set("company_country", companyCountry);
      }

      if (phoneCountry) {
        params.set("phone_country", phoneCountry);
      }

      if (mismatchOnly) {
        params.set("country_mismatch", "true");
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
            "Contacts could not be loaded.",
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
          : "An error occurred while loading contacts.",
      );
    } finally {
      setLoading(false);
    }
  }, [activeSearch, companyCountry, phoneCountry, mismatchOnly, page, pageSize, status]);

  useEffect(() => {
    void loadContacts();
  }, [loadContacts]);

  useEffect(() => {
    async function loadCountries() {
      try {
        const [companyResponse, phoneResponse] = await Promise.all([
          fetch(`${API_URL}/contacts/countries?field=company`, {
            cache: "no-store",
          }),
          fetch(`${API_URL}/contacts/countries?field=phone&has_phone=true`, {
            cache: "no-store",
          }),
        ]);

        if (companyResponse.ok) {
          const data = (await companyResponse.json()) as {
            items: CountryOption[];
          };
          setCompanyCountries(data.items);
        }

        if (phoneResponse.ok) {
          const data = (await phoneResponse.json()) as {
            items: CountryOption[];
          };
          setPhoneCountries(data.items);
        }
      } catch {
        setCompanyCountries([]);
        setPhoneCountries([]);
      }
    }

    void loadCountries();
  }, []);

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
    setCompanyCountry("");
    setPhoneCountry("");
    setMismatchOnly(false);
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

  function handleCompanyCountryChange(
    event: ChangeEvent<HTMLSelectElement>,
  ) {
    setCompanyCountry(event.target.value);
    setPage(1);
    setNotice(null);
    setSelectedIds([]);
  }

  function handlePhoneCountryChange(
    event: ChangeEvent<HTMLSelectElement>,
  ) {
    setPhoneCountry(event.target.value);
    setPage(1);
    setNotice(null);
    setSelectedIds([]);
  }

  function handlePageSizeChange(
    event: ChangeEvent<HTMLSelectElement>,
  ) {
    setPageSize(Number(event.target.value));
    setPage(1);
    setSelectedIds([]);
    setNotice(null);
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
          title: "Selection limit reached.",
          message:
            `You can select a maximum of ${MAX_SELECTED} contacts.`,
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
        title: `The most selected ${MAX_SELECTED} contacts.`,
        message:
          `There are multiple contacts on the current page, so the system selected the first ones. ${MAX_SELECTED}.`,
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
        title: "There are no contacts to process.",
        message:
          data.message ??
          "There are no matching contacts for phone number search.",
      });

      return;
    }

    setNotice({
      type:
        data.failed > 0
          ? "info"
          : "success",
      title: `Contacts processed: ${data.processed}`,
      message: [
        `found ${data.matched}`,
        `partially ${data.partial_match}`,
        `not found ${data.not_found}`,
        `skipped ${data.skipped}`,
        `errors ${data.failed}`,
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
          "The phone number could not be found.",
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
        title: "TThe phone number is found.",
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
        title: "The contact was skipped.",
        message:
          data.result.error ??
          "The contact uses a public email provider.",
      });

      return data;
    }

    if (data.result.status === "NOT_FOUND") {
      setNotice({
        type: "info",
        title: "The phone number was not found.",
        message:
          "The system scanned the accessible pages but did not find a valid number.",
      });

      return data;
    }

    setNotice({
      type: "error",
      title: "Search failed.",
      message:
        data.result.error ??
        "An error occurred while searching.",
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
        title: "Search failed.",
        message:
          err instanceof Error
            ? err.message
            : "An error occurred while searching.",
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
      title: `Contacts processed: ${contactsToProcess.length}`,
      message: [
        `phone found ${matched}`,
        `without a phone ${partialMatch + notFound + skipped}`,
        `errors ${failed}`,
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
        limit: String(pageSize),
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
            "Bulk processing could not be performed.",
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
        title: "Bulk processing failed.",
        message:
          err instanceof Error
            ? err.message
            : "An error occurred during bulk processing.",
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
    <div className="ciDataPage ciContactsPage">
      <header className="pageHeader ciDataHeader">
        <div>
          <p className="eyebrow">CONTACTS</p>
          <h1>Contacts</h1>
          <p className="muted">
            Overview of contacts and found phone numbers.
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
              ? "I am processing contacts..."
              : `Process the following ${pageSize}`}
          </button>

          <button
            type="button"
            className="secondaryButton"
            onClick={() => void loadContacts()}
            disabled={loading || bulkLoading}
          >
            {loading
              ? "Refreshing..."
              : "Refresh data"}
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
            Close
          </button>
        </div>
      )}

      <section className="panel pagePanel">
        <div className="panelTop contactsPanelTop">
          <div>
            <h2>Contact list</h2>
            <p className="muted">
              Total{" "}
              {formatNumber(pagination.total)} contacts.
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
              placeholder="Search by email or domain"
              aria-label="Search contacts"
            />

            <select
              value={status}
              onChange={handleStatusChange}
              aria-label="Filter by status"
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

            <select
              value={companyCountry}
              onChange={handleCompanyCountryChange}
              aria-label="Filter by company country"
            >
              <option value="">All company countries</option>
              {companyCountries.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.flag ?? "🌍"}{" "}
                  {item.name ?? item.code} ({item.count})
                </option>
              ))}
            </select>

            <select
              value={phoneCountry}
              onChange={handlePhoneCountryChange}
              aria-label="Filter by phone country"
            >
              <option value="">All phone countries</option>
              {phoneCountries.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.flag ?? "☎"}{" "}
                  {item.name ?? item.code} ({item.count})
                </option>
              ))}
            </select>

            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <input
                type="checkbox"
                checked={mismatchOnly}
                onChange={(event) => {
                  setMismatchOnly(event.target.checked);
                  setPage(1);
                }}
              />
              Just cross-border
            </label>

            <button
              type="submit"
              disabled={loading || bulkLoading}
            >
              Išči
            </button>

            {(activeSearch || status || companyCountry || phoneCountry || mismatchOnly) && (
              <button
                type="button"
                className="ghostButton"
                onClick={clearFilters}
              >
                Clean
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
                Selected contacts:{" "}
                {selectedIds.length}
              </strong>
              <p>
                You can process up to{" "}
                {MAX_SELECTED} contacts.
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
                  ? "I'm looking for phone numbers..."
                  : "Find phones for selected"}
              </button>

              <button
                type="button"
                className="ghostButton"
                onClick={() => setSelectedIds([])}
                disabled={bulkLoading}
              >
                Clear selection
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="alert alertError panelAlert">
            <div>
              <strong>
                Contacts could not be displayed.
              </strong>
              <p>{error}</p>
            </div>

            <button
              type="button"
              className="smallButton"
              onClick={() => void loadContacts()}
            >
              
              Try again
            </button>
          </div>
        )}

        {loading ? (
          <div className="stateMessage largeState">
            <div className="spinner" />
            <p>Loading contacts...</p>
          </div>
        ) : contacts.length === 0 ? (
          <div className="stateMessage largeState">
            <h3>No results</h3>
            <p>
             No contacts could be found for the selected filters.
            </p>

            {(activeSearch || status || companyCountry || phoneCountry || mismatchOnly) && (
              <button
                type="button"
                className="secondaryButton"
                onClick={clearFilters}
              >
                Clear filters
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
                        aria-label="Select all contacts on the page"
                      />
                    </th>

                    <th>E-mail</th>
                    <th>Domain</th>
                    <th>Company country</th>
                    <th>Phone country</th>
                    <th>Phone</th>
                    <th>Status</th>
                    <th>Confidence</th>
                    <th>Type</th>
                    <th>Try</th>
                    <th>Last processing</th>
                    <th>Action</th>
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

                    const isPublicEmail =
                      (contact as GeoContact)
                        .person_match_type === "public_email" ||
                      contact.status === "PUBLIC_EMAIL";

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
                              isPublicEmail ||
                              bulkLoading ||
                              isEnriching
                            }
                            onChange={() =>
                              toggleContactSelection(
                                contact.id,
                              )
                            }
                            aria-label={`Select ${contact.email}`}
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
                          {(() => {
                            const geo = contact as GeoContact;

                            return (
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "7px",
                                  flexWrap: "wrap",
                                }}
                              >
                                <CountryIntelligence
                                  flag={geo.country_flag}
                                  name={geo.country_name}
                                  code={geo.country_code}
                                  confidence={geo.country_confidence}
                                  source={geo.country_source}
                                  evidence={geo.country_evidence}
                                  compact
                                />

                                {geo.country_mismatch && (
                                  <CrossBorderBadge />
                                )}
                              </div>
                            );
                          })()}
                        </td>

                        <td>
                          {(() => {
                            const geo = contact as GeoContact;

                            return geo.phone_country_code ? (
                              <span
                                title={
                                  geo.country_mismatch
                                    ? "The phone country is different from the company country."
                                    : "Telephone country"
                                }
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "6px",
                                  padding: "5px 7px",
                                  borderRadius: "9px",
                                  background: geo.country_mismatch
                                    ? "rgba(245, 158, 11, 0.10)"
                                    : "rgba(148, 163, 184, 0.06)",
                                  border: geo.country_mismatch
                                    ? "1px solid rgba(245, 158, 11, 0.24)"
                                    : "1px solid rgba(148, 163, 184, 0.18)",
                                }}
                              >
                                {geo.phone_country_flag ?? "☎"}{" "}
                                {geo.phone_country_name ??
                                  geo.phone_country_code}
                              </span>
                            ) : (
                              "—"
                            );
                          })()}
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
                          {(() => {
                            const displayStatus = getDisplayStatus(
                              contact.status,
                              contact.phone,
                              contact.domain,
                            );

                            return (
                              <span
                                className={`statusBadge ${getStatusClass(
                                  displayStatus,
                                )}`}
                              >
                                {isEnriching
                                  ? "I am processing"
                                  : getStatusLabel(displayStatus)}
                              </span>
                            );
                          })()}
                        </td>

                        <td>
                          <ConfidenceBadge
                            value={contact.confidence}
                          />
                        </td>

                        <td>
                          <MatchTypeBadge
                            type={
                              (contact as GeoContact)
                                .person_match_type
                            }
                          />
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
                              isPublicEmail ||
                              bulkLoading
                            }
                            onClick={() =>
                              void handleSingleEnrichment(
                                contact,
                              )
                            }
                          >
                            {isEnriching
                              ? "Searching …"
                              : isPublicEmail
                                ? "Public e-mail"
                                : hasPhone
                                  ? "Search again"
                                  : "Find phone"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="paginationBar">
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: "16px",
      flexWrap: "wrap",
    }}
  >
    <p className="paginationInfo">
      Showing{" "}
      <strong>
        {formatNumber(resultStart)}–
        {formatNumber(resultEnd)}
      </strong>{" "}
      od{" "}
      <strong>
        {formatNumber(pagination.total)}
      </strong>
    </p>

    <label
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
      }}
    >
      <span className="muted">
        To the side:
      </span>

      <select
        value={pageSize}
        onChange={handlePageSizeChange}
        disabled={loading || bulkLoading}
      >
        {PAGE_SIZE_OPTIONS.map((size) => (
          <option
            key={size}
            value={size}
          >
            {size}
          </option>
        ))}
      </select>
    </label>
  </div>

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
                  Previous
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
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      <EnrichmentDrawer
        progress={bulkProgress}
        percentage={progressPercentage}
        onClose={() =>
          setBulkProgress(initialBulkProgress)
        }
      />


    </div>
  );
}