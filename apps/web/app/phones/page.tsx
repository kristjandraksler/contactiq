"use client";

import {
  ChangeEvent,
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  API_URL,
  DEFAULT_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
} from "../contacts/constants";

type Lead = {
  id: string;
  email: string;
  domain: string;
  website: string | null;
  phone: string | null;
  confidence: number | null;
  source_url: string | null;
  pages_scanned: number;
  scan_attempts: number;
  scan_duration_ms: number;
  last_scan: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  country_code?: string | null;
  country_name?: string | null;
  country_flag?: string | null;
  country_confidence?: number | null;
  country_source?: string | null;
};

type CountryOption = {
  code: string;
  name: string | null;
  flag: string | null;
  count: number;
};

type Pagination = {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_previous: boolean;
  has_next: boolean;
};

type LeadsResponse = {
  items: Lead[];
  pagination: Pagination;
  filters: {
    search: string | null;
    has_phone: boolean | null;
    confidence_min: number | null;
    status: string | null;
    country?: string | null;
  };
};

function formatNumber(value: number) {
  return new Intl.NumberFormat("sl-SI").format(value);
}

function formatDate(value: string | null) {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat("sl-SI", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getConfidenceLabel(confidence: number | null) {
  if (confidence === null) {
    return "—";
  }

  return `${confidence}%`;
}

function getPageNumbers(
  currentPage: number,
  totalPages: number,
) {
  if (totalPages <= 1) {
    return totalPages === 1 ? [1] : [];
  }

  const start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, currentPage + 2);

  const pages: number[] = [];

  for (let page = start; page <= end; page += 1) {
    pages.push(page);
  }

  return pages;
}

async function readErrorMessage(
  response: Response,
  fallback: string,
) {
  try {
    const data = await response.json();

    if (
      typeof data?.detail === "string" &&
      data.detail.trim()
    ) {
      return data.detail;
    }
  } catch {
    return fallback;
  }

  return fallback;
}

export default function PhonesPage() {
  const [leads, setLeads] = useState<Lead[]>([]);

  const [pagination, setPagination] =
    useState<Pagination>({
      page: 1,
      page_size: DEFAULT_PAGE_SIZE,
      total: 0,
      total_pages: 0,
      has_previous: false,
      has_next: false,
    });

  const [page, setPage] = useState(1);

  const [pageSize, setPageSize] = useState(
    DEFAULT_PAGE_SIZE,
  );

  const [searchInput, setSearchInput] = useState("");
  const [activeSearch, setActiveSearch] = useState("");

  const [confidenceMin, setConfidenceMin] =
    useState("");

  const [country, setCountry] = useState("");
  const [countries, setCountries] =
    useState<CountryOption[]>([]);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(
    null,
  );

  const loadPhones = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        has_phone: "true",
      });

      if (activeSearch.trim()) {
        params.set("search", activeSearch.trim());
      }

      if (confidenceMin) {
        params.set("confidence_min", confidenceMin);
      }

      if (country) {
        params.set("country", country);
      }

      const response = await fetch(
        `${API_URL}/leads?${params.toString()}`,
        {
          cache: "no-store",
        },
      );

      if (!response.ok) {
        throw new Error(
          await readErrorMessage(
            response,
            "Telefonov ni bilo mogoče naložiti.",
          ),
        );
      }

      const data: LeadsResponse = await response.json();

      setLeads(data.items);
      setPagination(data.pagination);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Pri nalaganju telefonov je prišlo do napake.",
      );
    } finally {
      setLoading(false);
    }
  }, [
    activeSearch,
    confidenceMin,
    country,
    page,
    pageSize,
  ]);

  useEffect(() => {
    void loadPhones();
  }, [loadPhones]);

  useEffect(() => {
    async function loadCountries() {
      try {
        const response = await fetch(
          `${API_URL}/contacts/countries?has_phone=true`,
          { cache: "no-store" },
        );

        if (!response.ok) {
          return;
        }

        const data = (await response.json()) as {
          items: CountryOption[];
        };

        setCountries(data.items);
      } catch {
        setCountries([]);
      }
    }

    void loadCountries();
  }, []);

  function handleSearch(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setPage(1);
    setActiveSearch(searchInput);
  }

  function clearFilters() {
    setSearchInput("");
    setActiveSearch("");
    setConfidenceMin("");
    setCountry("");
    setPage(1);
  }

  function handleConfidenceChange(
    event: ChangeEvent<HTMLSelectElement>,
  ) {
    setConfidenceMin(event.target.value);
    setPage(1);
  }

  function handleCountryChange(
    event: ChangeEvent<HTMLSelectElement>,
  ) {
    setCountry(event.target.value);
    setPage(1);
  }

  function handlePageSizeChange(
    event: ChangeEvent<HTMLSelectElement>,
  ) {
    setPageSize(Number(event.target.value));
    setPage(1);
  }

  function handleExportCsv() {
    const params = new URLSearchParams({
      has_phone: "true",
    });

    if (activeSearch.trim()) {
      params.set("search", activeSearch.trim());
    }

    if (confidenceMin) {
      params.set("confidence_min", confidenceMin);
    }

    if (country) {
      params.set("country", country);
    }

    window.location.href =
      `${API_URL}/leads/export/csv?${params.toString()}`;
  }

  async function copyToClipboard(
    value: string,
  ) {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      setError(
        "Podatka ni bilo mogoče kopirati v odložišče.",
      );
    }
  }

  const pageNumbers = useMemo(
    () =>
      getPageNumbers(
        pagination.page,
        pagination.total_pages,
      ),
    [pagination.page, pagination.total_pages],
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
          <p className="eyebrow">LEAD CENTER</p>
          <h1>Phones</h1>
          <p className="muted">
            Pregled vseh kontaktov z najdeno
            telefonsko številko.
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
            className="secondaryButton"
            onClick={() => void loadPhones()}
            disabled={loading}
          >
            {loading
              ? "Osvežujem …"
              : "Osveži podatke"}
          </button>

          <button
            type="button"
            onClick={handleExportCsv}
            disabled={loading || pagination.total === 0}
          >
            Export CSV
          </button>
        </div>
      </header>

      <section className="panel pagePanel">
        <div className="panelTop contactsPanelTop">
          <div>
            <h2>Najdeni telefoni</h2>

            <p className="muted">
              Skupaj{" "}
              {formatNumber(pagination.total)} rezultatov.
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
              placeholder="Išči po telefonu, e-mailu ali domeni"
              aria-label="Išči telefone"
            />

            <select
              value={confidenceMin}
              onChange={handleConfidenceChange}
              aria-label="Najnižji confidence"
            >
              <option value="">Vsi confidence</option>
              <option value="40">40% ali več</option>
              <option value="50">50% ali več</option>
              <option value="70">70% ali več</option>
              <option value="90">90% ali več</option>
            </select>

            <select
              value={country}
              onChange={handleCountryChange}
              aria-label="Filtriraj po državi"
            >
              <option value="">Vse države</option>

              {countries.map((item) => (
                <option
                  key={item.code}
                  value={item.code}
                >
                  {item.flag ?? "🌍"}{" "}
                  {item.name ?? item.code} ({item.count})
                </option>
              ))}
            </select>

            <button type="submit" disabled={loading}>
              Išči
            </button>

            {(activeSearch ||
              confidenceMin ||
              country) && (
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

        {error && (
          <div className="alert alertError panelAlert">
            <div>
              <strong>
                Telefonov ni bilo mogoče prikazati.
              </strong>

              <p>{error}</p>
            </div>

            <button
              type="button"
              className="smallButton"
              onClick={() => void loadPhones()}
            >
              Poskusi znova
            </button>
          </div>
        )}

        {loading ? (
          <div className="stateMessage largeState">
            <div className="spinner" />
            <p>Nalaganje telefonov …</p>
          </div>
        ) : leads.length === 0 ? (
          <div className="stateMessage largeState">
            <h3>Ni rezultatov</h3>

            <p>
              Za izbrane filtre ni bilo mogoče najti
              telefonov.
            </p>

            {(activeSearch ||
              confidenceMin ||
              country) && (
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
                    <th>Telefon</th>
                    <th>E-mail</th>
                    <th>Domena</th>
                    <th>Država</th>
                    <th>Confidence</th>
                    <th>Status</th>
                    <th>Vir</th>
                    <th>Zadnja obdelava</th>
                    <th>Akcije</th>
                  </tr>
                </thead>

                <tbody>
                  {leads.map((lead) => (
                    <tr key={lead.id}>
                      <td>
                        {lead.phone ? (
                          <a
                            href={`tel:${lead.phone}`}
                            className="tableLink"
                          >
                            {lead.phone}
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>

                      <td>
                        <strong className="emailCell">
                          {lead.email}
                        </strong>
                      </td>

                      <td>
                        {lead.website ? (
                          <a
                            href={lead.website}
                            target="_blank"
                            rel="noreferrer"
                            className="tableLink"
                          >
                            {lead.domain}
                          </a>
                        ) : (
                          lead.domain
                        )}
                      </td>

                      <td>
                        {lead.country_code ? (
                          <span
                            title={
                              lead.country_source
                                ? `Vir: ${lead.country_source}${
                                    lead.country_confidence !== null &&
                                    lead.country_confidence !== undefined
                                      ? ` · ${lead.country_confidence}%`
                                      : ""
                                  }`
                                : undefined
                            }
                          >
                            {lead.country_flag ?? "🌍"}{" "}
                            {lead.country_name ??
                              lead.country_code}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>

                      <td>
                        {getConfidenceLabel(
                          lead.confidence,
                        )}
                      </td>

                      <td>
                        <span className="statusBadge">
                          {lead.status}
                        </span>
                      </td>

                      <td>
                        {lead.source_url ? (
                          <a
                            href={lead.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="tableLink"
                          >
                            Odpri vir
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>

                      <td>
                        {formatDate(lead.last_scan)}
                      </td>

                      <td>
                        <div
                          style={{
                            display: "flex",
                            gap: "8px",
                            flexWrap: "wrap",
                          }}
                        >
                          {lead.phone && (
                            <button
                              type="button"
                              className="smallButton"
                              onClick={() =>
                                void copyToClipboard(
                                  lead.phone!,
                                )
                              }
                            >
                              Kopiraj telefon
                            </button>
                          )}

                          <button
                            type="button"
                            className="ghostButton"
                            onClick={() =>
                              void copyToClipboard(
                                lead.email,
                              )
                            }
                          >
                            Kopiraj e-mail
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
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

                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <span className="muted">
                    Na stran:
                  </span>

                  <select
                    value={pageSize}
                    onChange={handlePageSizeChange}
                    disabled={loading}
                  >
                    {PAGE_SIZE_OPTIONS.map(
                      (size) => (
                        <option
                          key={size}
                          value={size}
                        >
                          {size}
                        </option>
                      ),
                    )}
                  </select>
                </label>
              </div>

              <div className="paginationControls">
                <button
                  type="button"
                  className="paginationButton"
                  disabled={
                    !pagination.has_previous ||
                    loading
                  }
                  onClick={() =>
                    setPage((current) =>
                      Math.max(1, current - 1),
                    )
                  }
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
                        onClick={() =>
                          setPage(pageNumber)
                        }
                        disabled={loading}
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
                    loading
                  }
                  onClick={() =>
                    setPage(
                      (current) => current + 1,
                    )
                  }
                >
                  Naslednja
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}