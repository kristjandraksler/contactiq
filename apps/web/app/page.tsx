const stats = [
  { label: "Vsi e-maili", value: "32.481" },
  { label: "Ujemanja", value: "0" },
  { label: "Delna ujemanja", value: "0" },
  { label: "Ni najdeno", value: "0" },
];

export default function Home() {
  return (
    <>
      <header>
        <div>
          <p className="eyebrow">INTERNO ORODJE</p>
          <h1>Pregled kontaktov</h1>
          <p className="muted">Poišči javno objavljene telefonske številke za e-maile v bazi.</p>
        </div>
        <button>Začni obogatitev</button>
      </header>

      <div className="stats">
        {stats.map((stat) => (
          <article key={stat.label}>
            <span>{stat.label}</span>
            <strong>{stat.value}</strong>
          </article>
        ))}
      </div>

      <section className="panel">
        <div className="panelTop">
          <div>
            <h2>Zadnji kontakti</h2>
            <p className="muted">Trenutno so prikazani testni podatki.</p>
          </div>
        </div>
      </section>
    </>
  );
}
