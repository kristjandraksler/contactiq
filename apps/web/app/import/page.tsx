export default function ImportPage() {
  return (
    <>
      <header>
        <div>
          <p className="eyebrow">UVOZ</p>
          <h1>Uvoz e-mailov</h1>
          <p className="muted">V naslednjem koraku dodamo uvoz CSV, XLSX in TXT datotek.</p>
        </div>
      </header>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Naloži datoteko</h2>
            <p className="muted">Funkcija še ni povezana z API-jem.</p>
          </div>
          <button disabled>Izberi datoteko</button>
        </div>
      </section>
    </>
  );
}
