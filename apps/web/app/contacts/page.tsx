export default function ContactsPage() {
  return (
    <>
      <header>
        <div>
          <p className="eyebrow">KONTAKTI</p>
          <h1>Kontakti</h1>
          <p className="muted">Pregled e-mailov, telefonov in kakovosti ujemanja.</p>
        </div>
      </header>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Seznam kontaktov</h2>
            <p className="muted">Podatke bomo povezali s Supabase v naslednjem koraku.</p>
          </div>
          <input placeholder="Išči po e-mailu ali telefonu" />
        </div>
      </section>
    </>
  );
}
