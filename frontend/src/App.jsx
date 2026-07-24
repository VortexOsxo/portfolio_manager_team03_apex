import { useEffect, useState } from "react";

function App() {
  const [holdings, setHoldings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [tradeType, setTradeType] = useState("buy");
  const [ticker, setTicker] = useState("");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [tradeError, setTradeError] = useState(null);

  const fetchHoldings = () => {
    setLoading(true);
    fetch("/api/stocks/")
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        return res.json();
      })
      .then((data) => setHoldings(Object.values(data)))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchHoldings();
  }, []);

  const totalValue = holdings.reduce((sum, h) => sum + (h.value ?? 0), 0);

  const handleTrade = (e) => {
    e.preventDefault();
    setTradeError(null);
    setSubmitting(true);

    fetch(`/api/stocks/${tradeType}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: ticker.toUpperCase(), amount: Number(amount) }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`${tradeType} failed (status ${res.status})`);
        return res.json();
      })
      .then(() => {
        setTicker("");
        setAmount("");
        fetchHoldings();
      })
      .catch((err) => setTradeError(err.message))
      .finally(() => setSubmitting(false));
  };

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
            Holdings
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
            <p className="summary-value">${totalValue.toFixed(2)}</p>
          </article>

          <article className="summary-card">
            <p className="summary-label">Overall return</p>
            <p className="summary-value">—</p>
          </article>
        </section>

        <section className="holdings-card" id="holdings">
          <div className="card-heading">
            <h2>Current holdings</h2>
            <p>{holdings.length} positions</p>
          </div>

          <div className="table-wrapper">
            {loading && <p>Loading...</p>}
            {error && <p className="error">Failed to load holdings: {error}</p>}

            {!loading && !error && (
              <table>
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Name</th>
                    <th>Amount</th>
                    <th>Price</th>
                    <th>Value</th>
                  </tr>
                </thead>

                <tbody>
                  {holdings.map((holding) => (
                    <tr key={holding.ticker}>
                      <td className="ticker">{holding.ticker}</td>
                      <td>{holding.name}</td>
                      <td>{holding.amount}</td>
                      <td>{holding.current_price != null ? `$${Number(holding.current_price).toFixed(2)}` : "—"}</td>
                      <td>{holding.value != null ? `$${Number(holding.value).toFixed(2)}` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <form className="trade-form" onSubmit={handleTrade}>
            <h3>Buy / Sell</h3>

            <div className="trade-toggle">
              <button
                type="button"
                className={tradeType === "buy" ? "active" : ""}
                onClick={() => setTradeType("buy")}
              >
                Buy
              </button>
              <button
                type="button"
                className={tradeType === "sell" ? "active" : ""}
                onClick={() => setTradeType("sell")}
              >
                Sell
              </button>
            </div>

            <div className="trade-fields">
              <input
                type="text"
                placeholder="Ticker (e.g. AAPL)"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                required
              />

              <input
                type="number"
                placeholder="Amount"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                min="0"
                step="any"
                required
              />

              <button type="submit" disabled={submitting}>
                {submitting ? "Submitting..." : tradeType === "buy" ? "Buy" : "Sell"}
              </button>
            </div>

            {tradeError && <p className="error">{tradeError}</p>}
          </form>
        </section>
      </main>
    </div>
  );
}

export default App;