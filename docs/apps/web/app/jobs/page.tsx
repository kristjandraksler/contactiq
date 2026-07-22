export default function JobsPage() {
  return (
    <>
      <header>
        <div>
          <p className="eyebrow">OPRAVILA</p>
          <h1>Opravila</h1>
          <p className="muted">Spremljanje obdelave e-mailov in crawler opravil.</p>
        </div>
      </header>

      <section className="panel pagePanel">
        <div className="panelTop">
          <div>
            <h2>Ni aktivnih opravil</h2>
            <p className="muted">Ko bo worker povezan, bodo tukaj prikazani napredek in napake.</p>
          </div>
        </div>
      </section>
    </>
  );
}
