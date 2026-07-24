export default function SettingsPage() {
  return (
    <>
      <header>
        <div>
          <p className="eyebrow">NASTAVITVE</p>
          <h1>Konfiguracija sistema</h1>
          <p className="muted">
            Upravljajte nastavitve ContactIQ in pregled stanja sistema.
          </p>
        </div>
      </header>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Status sistema</h2>
            <p className="muted">
              Trenutno stanje ključnih storitev ContactIQ.
            </p>
          </div>
        </div>

        <table className="settingsTable">
          <tbody>
            <tr>
              <td>API</td>
              <td>🟢 Online</td>
            </tr>
            <tr>
              <td>Supabase</td>
              <td>🟢 Connected</td>
            </tr>
            <tr>
              <td>Website Crawler</td>
              <td>🟢 Ready</td>
            </tr>
            <tr>
              <td>Company Cache</td>
              <td>🟢 Active</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Baza podatkov</h2>
            <p className="muted">
              Status povezave s Supabase ter osnovne informacije o podatkovni
              bazi.
            </p>
          </div>
        </div>
      </section>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Enrichment</h2>
            <p className="muted">
              Nastavitve Website Crawlerja, Company Cache in obdelave domen.
            </p>
          </div>
        </div>
      </section>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Sistem</h2>
            <p className="muted">
              Informacije o aplikaciji, API-ju in konfiguraciji.
            </p>
          </div>
        </div>
      </section>

      <section className="panel pagePanel">
  <div className="panelTop">
    <div>
      <h2>Vzdrževanje</h2>
      <p className="muted">
        Orodja za vzdrževanje sistema bodo na voljo v eni izmed prihodnjih različic.
      </p>
    </div>
  </div>

  <p className="muted" style={{ marginTop: "16px" }}>
    Trenutna različica ContactIQ samodejno upravlja Company Cache, obdelavo
    kontaktov in ponovne poskuse. Dodatna administratorska orodja bodo dodana
    v prihodnjih posodobitvah.
  </p>
</section>
    </>
  );
}