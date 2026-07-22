export default function SettingsPage() {
  return (
    <>
      <header>
        <div>
          <p className="eyebrow">NASTAVITVE</p>
          <h1>Nastavitve</h1>
          <p className="muted">Nastavitve crawlerja, API povezav in uporabniškega dostopa.</p>
        </div>
      </header>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Konfiguracija</h2>
            <p className="muted">Povezavo s Supabase bomo dodali v naslednjem koraku.</p>
          </div>
        </div>
      </section>
    </>
  );
}
