"use client";

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
  person_match_type?: string | null;
  phone_country_code?: string | null;
  phone_country_name?: string | null;
  phone_country_flag?: string | null;
  phone_country_confidence?: number | null;
  country_mismatch?: boolean;
  is_cross_border?: boolean;
};

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
        title: `Izbranih je največ ${MAX_SELECTED} kontaktov.`,
        message:
          `Na trenutni strani je več kontaktov, zato je sistem izbral prvih ${MAX_SELECTED}.`,
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
        `telefon najden ${matched}`,
        `brez telefona ${partialMatch + notFound + skipped}`,
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
            Pregled kontaktov in najdenih telefonskih številk.
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
              : `Obdelaj naslednjih ${pageSize}`}
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

            <select
              value={companyCountry}
              onChange={handleCompanyCountryChange}
              aria-label="Filtriraj po državi podjetja"
            >
              <option value="">Vse države podjetij</option>
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
              aria-label="Filtriraj po državi telefona"
            >
              <option value="">Vse države telefonov</option>
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
              Samo cross-border
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

            {(activeSearch || status || companyCountry || phoneCountry || mismatchOnly) && (
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
                    <th>Država podjetja</th>
                    <th>Država telefona</th>
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
                          {(() => {
                            const geo = contact as GeoContact;

                            return geo.country_code ? (
                              <span
                                title={
                                  geo.country_source
                                    ? `Vir: ${geo.country_source}${
                                        geo.country_confidence !== null &&
                                        geo.country_confidence !== undefined
                                          ? ` · ${geo.country_confidence}%`
                                          : ""
                                      }`
                                    : undefined
                                }
                              >
                                {geo.country_flag ?? "🌍"}{" "}
                                {geo.country_code}
                              </span>
                            ) : (
                              "—"
                            );
                          })()}
                        </td>

                        <td>
                          {(() => {
                            const geo = contact as GeoContact;

                            return geo.phone_country_code ? (
                              <span>
                                {geo.phone_country_flag ?? "☎"}{" "}
                                {geo.phone_country_code}
                                {geo.country_mismatch ? " ⚠" : ""}
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
                                  ? "Obdelujem"
                                  : getStatusLabel(displayStatus)}
                              </span>
                            );
                          })()}
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
        Na stran:
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

      <EnrichmentDrawer
        progress={bulkProgress}
        percentage={progressPercentage}
        onClose={() =>
          setBulkProgress(initialBulkProgress)
        }
      />


    </>
  );
}