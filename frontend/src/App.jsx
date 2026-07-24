// Holding data is hardcore just o try out how it looks
const holdings = [
  {
    holding_id: 1,
    ticker: "TSLA",
    amount: 50,
    cost_basis: 225.4,
    purchase_date: "2026-07-01",
  },
  {
    holding_id: 2,
    ticker: "AAPL",
    amount: 120,
    cost_basis: 190.25,
    purchase_date: "2026-07-10",
  },
  {
    holding_id: 3,
    ticker: "MSFT",
    amount: 85,
    cost_basis: 480.75,
    purchase_date: "2026-07-18",
  },
];

function App() {
  return (
    <div className="app-shell">
      <header className="navbar">
        <a className="brand" href="/">
          Portfolio Manager 
        </a>

        <nav className="navigation" aria-label="Main navigation">
          <a className="nav-link active" href="#overview">
            Overview
          </a>

          <a className="nav-link" href="#holdings">
            Holdings (coming soon)
          </a>

          <a className="nav-link" href="#performance">
            Performance (coming soon)
          </a>

          <div className="avatar" aria-label="Eduardo profile">
            EP
            </div>
        </nav>
      </header>

      <main className="dashboard">
        <section className="page-heading" id="overview">
          <h1>My portfolio</h1>
          <p>A snapshot of your holdings</p>
        </section>

        <section className="summary-grid" aria-label="Portfolio summary">
          <article className="summary-card">
            <p className="summary-label">Total value</p>
            <p className="summary-value">-</p>
          </article>

          <article className="summary-card">
            <p className="summary-label">Overall return</p>
            <p className="summary-value">—</p>
          </article>
        </section>

        <section className="holdings-card" id="holdings">
          <div className="card-heading">
            <h2>Current holdings</h2>
            <p>{holdings.length} positions (dummy data)</p>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Amount</th>
                  <th>Cost </th>
                  <th>Purchase date</th>
                </tr>
              </thead>

              <tbody>
                {holdings.map((holding) => (
                  <tr key={holding.holding_id}>
                    <td className="ticker">{holding.ticker}</td>
                    <td>{holding.amount}</td>
                    <td>${Number(holding.cost_basis).toFixed(2)}</td>
                    <td>{holding.purchase_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;