export default function SettingsPage() {
  return (
    <>
      <header>
        <div>
          <p className="eyebrow">NASTAVITVE</p>
          <h1>Konfiguracija sistema</h1>
          <p className="muted">
            Upravljajte nastavitve ContactIQ, povezavo z bazo podatkov in
            parametre obdelave kontaktov.
          </p>
        </div>
      </header>

      <section className="statsGrid">
        <div className="statCard">
          <span className="statValue">🟢</span>
          <span className="statLabel">API Online</span>
        </div>

        <div className="statCard">
          <span className="statValue">🟢</span>
          <span className="statLabel">Supabase Connected</span>
        </div>

        <div className="statCard">
          <span className="statValue">🟢</span>
          <span className="statLabel">Crawler Ready</span>
        </div>

        <div className="statCard">
          <span className="statValue">🟢</span>
          <span className="statLabel">Company Cache Active</span>
        </div>
      </section>

      <section className="settingsGrid">
        <div className="panel">
          <h2>🗄️ Baza podatkov</h2>
          <p className="muted">
            Status povezave s Supabase ter osnovne informacije o bazi podatkov.
          </p>
        </div>

        <div className="panel">
          <h2>🔍 Enrichment</h2>
          <p className="muted">
            Nastavitve Website Crawlerja, Company Cache in obdelave domen.
          </p>
        </div>

        

        <div className="panel">
          <h2>⚙️ Sistem</h2>
          <p className="muted">
            Informacije o različici aplikacije, API storitvi in konfiguraciji.
          </p>
        </div>
      </section>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Vzdrževanje</h2>
            <p className="muted">
              Orodja za upravljanje sistema bodo na voljo v naslednji različici.
            </p>
          </div>
        </div>

        <div className="buttonRow">
          <button disabled>Počisti Company Cache</button>
          <button disabled>Ponovno obdelaj FAILED</button>
          <button disabled>Ponovno obdelaj NOT_FOUND</button>
        </div>
      </section>
    </>
  );
}