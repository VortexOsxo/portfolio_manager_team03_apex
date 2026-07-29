import { useEffect, useMemo, useRef, useState } from "react";

const formatCurrency = (value) => {
  if (value === null || value === undefined) return "—";
  const sign = value < 0 ? "-" : "";
  const formatted = Math.abs(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${sign}$${formatted}`;
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

const formatDate = (value) => {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return `${parsed.toLocaleDateString()} ${parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
};

function useCountUp(value, duration = 600) {
  const [display, setDisplay] = useState(value ?? 0);
  const prevRef = useRef(value ?? 0);

  useEffect(() => {
    if (value == null) return undefined;
    const from = prevRef.current;
    const to = value;
    const start = performance.now();
    let raf;

    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(from + (to - from) * eased);
      if (progress < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        prevRef.current = to;
      }
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return value == null ? null : display;
}

function TrendArrow({ value }) {
  if (!value) return null;
  const up = value > 0;
  return (
    <svg
      className={`trend-arrow ${up ? "positive" : "negative"}`}
      width="9"
      height="9"
      viewBox="0 0 10 10"
      aria-hidden="true"
    >
      <path d={up ? "M5 0 L10 8 L0 8 Z" : "M5 10 L0 2 L10 2 Z"} fill="currentColor" />
    </svg>
  );
}

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
  const [tickerResults, setTickerResults] = useState([]);

  const [historyTicker, setHistoryTicker] = useState(null);
  const [historyTransactions, setHistoryTransactions] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [modalClosing, setModalClosing] = useState(false);

  const animatedTotalValue = useCountUp(summary?.total_value ?? null);
  const animatedUnrealizedPnl = useCountUp(summary?.total_unrealized_pnl ?? null);
  const animatedDayChange = useCountUp(summary?.total_day_change ?? null);
  const animatedRealizedPnl = useCountUp(summary?.total_realized_pnl ?? null);

  const fetchHoldings = () => {
    setLoading(true);
    setError(null);
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

  useEffect(() => {
    // selling only happens to what we already own, so no need to search for tickers when selling
    if (tradeType === "sell" || !ticker.trim()) {
      setTickerResults([]);
      return;
    }

    const handle = setTimeout(() => {
      fetch(`/api/stocks/search?q=${encodeURIComponent(ticker)}`)
        .then((res) => (res.ok ? res.json() : []))
        .then((data) => setTickerResults(data))
        .catch(() => setTickerResults([]));
    }, 300);

    return () => clearTimeout(handle);
  }, [ticker, tradeType]);

  const tickerLookup = useMemo(() => {
    const map = new Map();
    holdings.forEach((h) => map.set(h.ticker, h.name));
    if (tradeType !== "sell") {
      tickerResults.forEach((r) => map.set(r.ticker, r.name));
    }
    return map;
  }, [holdings, tickerResults, tradeType]);

  const isValidTicker = tickerLookup.has(ticker.toUpperCase());

  const handleTickerChange = (e) => {
    setTicker(e.target.value);
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

  const openHistory = (tickerSymbol) => {
    setHistoryTicker(tickerSymbol);
    setHistoryTransactions([]);
    setHistoryError(null);
    setHistoryLoading(true);

    fetch(`/api/transactions/?ticker=${encodeURIComponent(tickerSymbol)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        return res.json();
      })
      .then((data) => setHistoryTransactions(data))
      .catch((err) => setHistoryError(err.message))
      .finally(() => setHistoryLoading(false));
  };

  const closeHistory = () => {
    setModalClosing(true);
    setTimeout(() => {
      setHistoryTicker(null);
      setHistoryTransactions([]);
      setHistoryError(null);
      setModalClosing(false);
    }, 180);
  };

  return (
    <div className="app-shell">
      <div className="grain-overlay" aria-hidden="true" />
      <header className="navbar">
        <a className="brand" href="/">
          <img className="brand-mark" src="/logo.png" alt="" aria-hidden="true" />
          Portfolio Manager
        </a>

        <nav className="navigation" aria-label="Main navigation">
          <span className="nav-link active" aria-current="page">
            Overview
          </span>

          <span className="nav-link disabled" aria-disabled="true">
            Performance (coming soon)
          </span>

          <div className="avatar" aria-label="Eduardo profile">
            EP
            </div>
        </nav>
      </header>

      <main className="dashboard">
        <section className="page-heading">
          <h1>My portfolio</h1>
          <p>A snapshot of your holdings</p>
        </section>

        <section className="summary-grid" aria-label="Portfolio summary">
          <article className="summary-card">
            <p className="summary-label">Total value</p>
            {loading && !summary ? (
              <p className="summary-value"><span className="skeleton-block" style={{ width: "90px", height: "22px" }} /></p>
            ) : (
              <p className="summary-value">{formatCurrency(animatedTotalValue)}</p>
            )}
          </article>

          <article className="summary-card">
            <p className="summary-label">Overall return</p>
            {loading && !summary ? (
              <p className="summary-value"><span className="skeleton-block" style={{ width: "90px", height: "22px" }} /></p>
            ) : (
              <p className={`summary-value ${signClass(summary?.total_unrealized_pnl)}`}>
                <TrendArrow value={summary?.total_unrealized_pnl} />
                {formatCurrency(animatedUnrealizedPnl)}
                {summary?.total_unrealized_pnl_pct != null && (
                  <span className="summary-sub">({formatPercent(summary.total_unrealized_pnl_pct)})</span>
                )}
              </p>
            )}
          </article>

          <article className="summary-card">
            <p className="summary-label">Today's change</p>
            {loading && !summary ? (
              <p className="summary-value"><span className="skeleton-block" style={{ width: "90px", height: "22px" }} /></p>
            ) : (
              <p className={`summary-value ${signClass(summary?.total_day_change)}`}>
                <TrendArrow value={summary?.total_day_change} />
                {formatCurrency(animatedDayChange)}
                {summary?.total_day_change_pct != null && (
                  <span className="summary-sub">({formatPercent(summary.total_day_change_pct)})</span>
                )}
              </p>
            )}
          </article>

          <article className="summary-card">
            <p className="summary-label">Realized P&amp;L</p>
            {loading && !summary ? (
              <p className="summary-value"><span className="skeleton-block" style={{ width: "90px", height: "22px" }} /></p>
            ) : (
              <p className={`summary-value ${signClass(summary?.total_realized_pnl)}`}>
                <TrendArrow value={summary?.total_realized_pnl} />
                {formatCurrency(animatedRealizedPnl)}
              </p>
            )}
          </article>
        </section>

        <section className="holdings-card">
          <div className="card-heading">
            <h2>Current holdings</h2>
            <p>{holdings.length} positions</p>
          </div>

          <div className="table-wrapper">
            {error && <p className="error">Failed to load holdings: {error}</p>}

            {loading && !error && (
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
                  {Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="skeleton-row" style={{ animationDelay: `${i * 60}ms` }}>
                      {Array.from({ length: 8 }).map((__, j) => (
                        <td key={j}><span className="skeleton-block" /></td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

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
                  {holdings.map((holding, i) => (
                    <tr
                      key={holding.ticker}
                      className="clickable-row"
                      style={{ animationDelay: `${i * 45}ms` }}
                      onClick={() => openHistory(holding.ticker)}
                    >
                      <td><span className="ticker-badge">{holding.ticker}</span></td>
                      <td>{holding.name}</td>
                      <td>{Number(holding.amount)}</td>
                      <td>{formatCurrency(holding.avg_cost)}</td>
                      <td>{formatCurrency(holding.current_price)}</td>
                      <td className={signClass(holding.day_change)}>
                        <span className="cell-with-icon">
                          <TrendArrow value={holding.day_change} />
                          {formatCurrency(holding.day_change)}
                          {holding.day_change_pct != null && <> ({formatPercent(holding.day_change_pct)})</>}
                        </span>
                      </td>
                      <td>{formatCurrency(holding.value)}</td>
                      <td className={signClass(holding.unrealized_pnl)}>
                        <span className="cell-with-icon">
                          <TrendArrow value={holding.unrealized_pnl} />
                          {formatCurrency(holding.unrealized_pnl)}
                          {holding.unrealized_pnl_pct != null && <> ({formatPercent(holding.unrealized_pnl_pct)})</>}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <form className="trade-form" onSubmit={handleTrade}>
            <h3>Buy / Sell</h3>

            <div className="trade-toggle" data-active={tradeType}>
              <span className="trade-toggle-pill" aria-hidden="true" />
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
                placeholder="Ticker or company name"
                value={ticker}
                onChange={handleTickerChange}
                autoComplete="off"
                required
              />
              <datalist id="ticker-options">
                {Array.from(tickerLookup.entries()).map(([t, name]) => (
                  <option key={t} value={t}>
                    {name}
                  </option>
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

        {historyTicker && (
          <div className={`modal-overlay ${modalClosing ? "closing" : ""}`} onClick={closeHistory}>
            <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <div>
                  <h3>{historyTicker}</h3>
                  <p>{tickerLookup.get(historyTicker)}</p>
                </div>
                <button type="button" className="modal-close" onClick={closeHistory} aria-label="Close">
                  &times;
                </button>
              </div>

              <div className="modal-body">
                {historyLoading && <p>Loading...</p>}
                {historyError && <p className="error">Failed to load history: {historyError}</p>}

                {!historyLoading && !historyError && historyTransactions.length === 0 && (
                  <p>No transactions found.</p>
                )}

                {!historyLoading && !historyError && historyTransactions.length > 0 && (
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Shares</th>
                        <th>Price</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...historyTransactions]
                        .sort((a, b) => new Date(b.transaction_date) - new Date(a.transaction_date) || b.tr_id - a.tr_id)
                        .map((tx) => {
                        const amountNum = Number(tx.amount);
                        const isBuy = amountNum > 0;
                        return (
                          <tr key={tx.tr_id}>
                            <td>{formatDate(tx.transaction_date)}</td>
                            <td className={isBuy ? "positive" : "negative"}>{isBuy ? "Buy" : "Sell"}</td>
                            <td>{Math.abs(amountNum)}</td>
                            <td>{formatCurrency(Number(tx.cost_basis))}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;