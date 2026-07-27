import { useEffect, useMemo, useState } from "react";

// Small set for the ticker autocomplete. Later inteded to be replaced with an API call
const KNOWN_TICKERS = [
  { ticker: "AAPL", name: "Apple Inc." },
  { ticker: "MSFT", name: "Microsoft Corporation" },
  { ticker: "GOOGL", name: "Alphabet Inc." },
  { ticker: "AMZN", name: "Amazon.com Inc." },
  { ticker: "NVDA", name: "NVIDIA Corporation" },
  { ticker: "TSLA", name: "Tesla Inc." },
  { ticker: "META", name: "Meta Platforms Inc." },
  { ticker: "NFLX", name: "Netflix Inc." },
  { ticker: "AMD", name: "Advanced Micro Devices Inc." },
  { ticker: "INTC", name: "Intel Corporation" },
  { ticker: "DIS", name: "The Walt Disney Company" },
  { ticker: "V", name: "Visa Inc." },
  { ticker: "JPM", name: "JPMorgan Chase & Co." },
  { ticker: "KO", name: "The Coca-Cola Company" },
  { ticker: "PEP", name: "PepsiCo Inc." },
];

const formatCurrency = (value) => {
  if (value === null || value === undefined) return "—";
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toFixed(2)}`;
};

const formatPercent = (value) => {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
};

const signClass = (value) => {
  if (!value) return "";
  return value > 0 ? "positive" : "negative";
};

function App() {
  const [holdings, setHoldings] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [tradeType, setTradeType] = useState("buy");
  const [ticker, setTicker] = useState("");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [tradeError, setTradeError] = useState(null);

  const fetchHoldings = () => {
    setLoading(true);
    Promise.all([
      fetch("/api/stocks/").then((res) => {
        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        return res.json();
      }),
      fetch("/api/stocks/summary").then((res) => {
        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        return res.json();
      }),
    ])
      .then(([stocksData, summaryData]) => {
        setHoldings(Object.values(stocksData));
        setSummary(summaryData);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchHoldings();
  }, []);

  const tickerOptions = useMemo(() => {
    const known = KNOWN_TICKERS.map((t) => t.ticker);
    const owned = holdings.map((h) => h.ticker);
    return Array.from(new Set([...known, ...owned])).sort();
  }, [holdings]);

  const isValidTicker = tickerOptions.includes(ticker.toUpperCase());

  const handleTickerChange = (e) => {
    setTicker(e.target.value.toUpperCase());
  };

  const handleAmountChange = (e) => {
    const value = e.target.value;
    if (/^\d*\.?\d*$/.test(value)) {
      setAmount(value);
    }
  };

  const handleTrade = (e) => {
    e.preventDefault();
    if (!isValidTicker) {
      setTradeError("Pick a ticker from the list");
      return;
    }
    setTradeError(null);
    setSubmitting(true);

    fetch(`/api/stocks/${tradeType}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: ticker.toUpperCase(), amount: Number(amount) }),
    })
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.error || `${tradeType} failed (status ${res.status})`);
        return body;
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
            <p className="summary-value">{formatCurrency(summary?.total_value)}</p>
          </article>

          <article className="summary-card">
            <p className="summary-label">Overall return</p>
            <p className={`summary-value ${signClass(summary?.total_unrealized_pnl)}`}>
              {formatCurrency(summary?.total_unrealized_pnl)}
              {summary?.total_unrealized_pnl_pct != null && (
                <> ({formatPercent(summary.total_unrealized_pnl_pct)})</>
              )}
            </p>
          </article>

          <article className="summary-card">
            <p className="summary-label">Today's change</p>
            <p className={`summary-value ${signClass(summary?.total_day_change)}`}>
              {formatCurrency(summary?.total_day_change)}
              {summary?.total_day_change_pct != null && (
                <> ({formatPercent(summary.total_day_change_pct)})</>
              )}
            </p>
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
                    <th>Avg cost</th>
                    <th>Price</th>
                    <th>Day change</th>
                    <th>Value</th>
                    <th>Unrealized P&amp;L</th>
                  </tr>
                </thead>

                <tbody>
                  {holdings.map((holding) => (
                    <tr key={holding.ticker}>
                      <td className="ticker">{holding.ticker}</td>
                      <td>{holding.name}</td>
                      <td>{Number(holding.amount)}</td>
                      <td>{formatCurrency(holding.avg_cost)}</td>
                      <td>{formatCurrency(holding.current_price)}</td>
                      <td className={signClass(holding.day_change)}>
                        {formatCurrency(holding.day_change)}
                        {holding.day_change_pct != null && <> ({formatPercent(holding.day_change_pct)})</>}
                      </td>
                      <td>{formatCurrency(holding.value)}</td>
                      <td className={signClass(holding.unrealized_pnl)}>
                        {formatCurrency(holding.unrealized_pnl)}
                        {holding.unrealized_pnl_pct != null && <> ({formatPercent(holding.unrealized_pnl_pct)})</>}
                      </td>
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
                list="ticker-options"
                placeholder="Ticker (e.g. AAPL)"
                value={ticker}
                onChange={handleTickerChange}
                autoComplete="off"
                required
              />
              <datalist id="ticker-options">
                {tickerOptions.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>

              <input
                type="text"
                inputMode="decimal"
                placeholder="Amount"
                value={amount}
                onChange={handleAmountChange}
                required
              />

              <button type="submit" disabled={submitting || !isValidTicker || !amount}>
                {submitting ? "Submitting..." : tradeType === "buy" ? "Buy" : "Sell"}
              </button>
            </div>

            {ticker && !isValidTicker && (
              <p className="error">"{ticker}" isn't a recognized ticker</p>
            )}
            {tradeError && <p className="error">{tradeError}</p>}
          </form>
        </section>
      </main>
    </div>
  );
}

export default App;