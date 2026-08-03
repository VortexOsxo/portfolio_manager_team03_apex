import { useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const PERFORMANCE_RANGES = [
  { label: "1M", months: 1 },
  { label: "3M", months: 3 },
  { label: "6M", months: 6 },
  { label: "1Y", months: 12 },
];

const PERFORMANCE_CACHE_TTL_MS = 5 * 60 * 1000;

const CHART_ACCENT = "#6d6cff";
const CHART_SURFACE = "#12142a";

const formatCurrency = (value) => {
  if (value === null || value === undefined) return "—";
  const sign = value < 0 ? "-" : "";
  const formatted = Math.abs(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${sign}$${formatted}`;
};

const formatAmountForDisplay = (raw) => {
  if (!raw) return "";
  const [intPart, decPart] = raw.split(".");
  const formattedInt = intPart === "" ? "" : Number(intPart).toLocaleString("en-US");
  return decPart !== undefined ? `${formattedInt}.${decPart}` : formattedInt;
};

const makeAmountChangeHandler = (setter, clearError) => (e) => {
  const input = e.target;
  const rawInput = input.value;
  const cursorPos = input.selectionStart ?? rawInput.length;
  const digitsBeforeCursor = rawInput.slice(0, cursorPos).replace(/[^\d.]/g, "").length;

  const stripped = rawInput.replace(/,/g, "");
  if (!/^\d*\.?\d*$/.test(stripped)) return;

  setter(stripped);
  if (clearError) clearError(null);

  requestAnimationFrame(() => {
    const formatted = formatAmountForDisplay(stripped);
    let seen = 0;
    let newPos = formatted.length;
    for (let i = 0; i < formatted.length; i += 1) {
      if (/\d|\./.test(formatted[i])) seen += 1;
      if (seen === digitsBeforeCursor) {
        newPos = i + 1;
        break;
      }
    }
    input.setSelectionRange(newPos, newPos);
  });
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

const formatChartDate = (value, options = { month: "short", day: "numeric" }) => {
  if (!value) return "—";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString(undefined, options);
};

const formatCompactCurrency = (value) => {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
};

const toApiDate = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const getPerformanceDates = (rangeLabel) => {
  const end = new Date();
  const start = new Date(end);
  const range = PERFORMANCE_RANGES.find((item) => item.label === rangeLabel);
  const originalDay = start.getDate();
  start.setDate(1);
  start.setMonth(start.getMonth() - (range?.months ?? 3));
  const lastDayOfMonth = new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate();
  start.setDate(Math.min(originalDay, lastDayOfMonth));
  return { startDate: toApiDate(start), endDate: toApiDate(end) };
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

function PerformanceTooltip({ active, payload, label, valueLabel = "Portfolio value" }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="chart-tooltip">
      <p>{formatChartDate(label, { month: "long", day: "numeric", year: "numeric" })}</p>
      <strong>{formatCurrency(payload[0].value)}</strong>
      <span>{valueLabel}</span>
    </div>
  );
}

function App() {
  const [activeView, setActiveView] = useState("overview");
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
  const [lookupError, setLookupError] = useState(null);

  const [fundType, setFundType] = useState("deposit");
  const [fundAmount, setFundAmount] = useState("");
  const [fundSubmitting, setFundSubmitting] = useState(false);
  const [fundError, setFundError] = useState(null);

  const [historyTicker, setHistoryTicker] = useState(null);
  const [historyTransactions, setHistoryTransactions] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [historyPerformance, setHistoryPerformance] = useState([]);
  const [historyPerformanceLoading, setHistoryPerformanceLoading] = useState(false);
  const [modalClosing, setModalClosing] = useState(false);
  const activeHistoryRequestRef = useRef(0);

  const [quote, setQuote] = useState(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState(null);

  const [showRealizedModal, setShowRealizedModal] = useState(false);
  const [realizedModalClosing, setRealizedModalClosing] = useState(false);

  const [showCashModal, setShowCashModal] = useState(false);
  const [cashModalClosing, setCashModalClosing] = useState(false);
  const [cashTransactions, setCashTransactions] = useState([]);
  const [cashTransactionsLoading, setCashTransactionsLoading] = useState(false);
  const [cashTransactionsError, setCashTransactionsError] = useState(null);

  const [performanceRange, setPerformanceRange] = useState("3M");
  const [performanceData, setPerformanceData] = useState([]);
  const [performanceLoading, setPerformanceLoading] = useState(false);
  const [performanceError, setPerformanceError] = useState(null);
  const [performanceRequestKey, setPerformanceRequestKey] = useState(0);
  const performanceCacheRef = useRef(new Map());

  // Computed once per range change, so the fetch and the displayed header
  // date range can't disagree if "now" ticks over a day between renders.
  const performanceDateRange = useMemo(() => getPerformanceDates(performanceRange), [performanceRange]);

  const animatedTotalValue = useCountUp(summary?.total_value ?? null);
  const animatedUnrealizedPnl = useCountUp(summary?.total_unrealized_pnl ?? null);
  const animatedDayChange = useCountUp(summary?.total_day_change ?? null);
  const animatedRealizedPnl = useCountUp(summary?.total_realized_pnl ?? null);
  const animatedCashBalance = useCountUp(summary?.cash_balance ?? null);

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
    if (!(historyTicker || showRealizedModal || showCashModal)) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [historyTicker, showRealizedModal, showCashModal]);

  useEffect(() => {
    if (activeView !== "performance") return undefined;

    const { startDate, endDate } = performanceDateRange;
    const cacheKey = `${startDate}:${endDate}`;
    const cached = performanceCacheRef.current.get(cacheKey);
    const isFresh = cached && Date.now() - cached.cachedAt < PERFORMANCE_CACHE_TTL_MS;

    if (isFresh) {
      setPerformanceData(cached.data);
      setPerformanceLoading(false);
      setPerformanceError(null);
      return undefined;
    }

    const controller = new AbortController();
    setPerformanceLoading(true);
    setPerformanceError(null);

    fetch(`/api/stocks/performance?start_date=${startDate}&end_date=${endDate}`, {
      signal: controller.signal,
    })
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.error || `Request failed: ${res.status}`);
        return body;
      })
      .then((data) => {
        const dates = Array.isArray(data.dates) ? data.dates : [];
        const equity = Array.isArray(data.equity) ? data.equity : [];
        const cash = Array.isArray(data.cash) ? data.cash : [];
        const chartData = dates
          .slice(0, equity.length)
          .map((date, index) => ({
            date,
            value: Number(equity[index]) + Number(cash[index] ?? 0),
          }))
          .filter((point) => Number.isFinite(point.value));
        performanceCacheRef.current.set(cacheKey, { data: chartData, cachedAt: Date.now() });
        setPerformanceData(chartData);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setPerformanceError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setPerformanceLoading(false);
      });

    return () => controller.abort();
  }, [activeView, performanceDateRange, performanceRequestKey]);

  useEffect(() => {
    if (!ticker.trim()) {
      setTickerResults([]);
      return undefined;
    }

    const controller = new AbortController();
    const handle = setTimeout(() => {
      fetch(`/api/stocks/search?q=${encodeURIComponent(ticker)}`, { signal: controller.signal })
        .then((res) => (res.ok ? res.json() : []))
        .then((data) => setTickerResults(Array.isArray(data) ? data : []))
        .catch((err) => {
          if (err.name !== "AbortError") setTickerResults([]);
        });
    }, 300);

    return () => {
      clearTimeout(handle);
      controller.abort();
    };
  }, [ticker]);

  const tickerLookup = useMemo(() => {
    const map = new Map();
    holdings.forEach((h) => map.set(h.ticker, h.name));
    tickerResults.forEach((r) => map.set(r.ticker, r.name));
    return map;
  }, [holdings, tickerResults]);

  const ownedHolding = historyTicker ? holdings.find((h) => h.ticker === historyTicker) : null;

  const realizedLots = summary?.realized_lots ?? [];

  const performanceStats = useMemo(() => {
    if (performanceData.length === 0) return null;

    const firstValue = performanceData[0].value;
    const currentValue = performanceData[performanceData.length - 1].value;
    const change = currentValue - firstValue;
    const changePct = firstValue ? (change / firstValue) * 100 : null;
    let bestDay = null;

    for (let i = 1; i < performanceData.length; i += 1) {
      const dayChange = performanceData[i].value - performanceData[i - 1].value;
      if (!bestDay || dayChange > bestDay.change) {
        bestDay = {
          change: dayChange,
          date: performanceData[i].date,
        };
      }
    }

    return { currentValue, change, changePct, bestDay };
  }, [performanceData]);

  const handleTickerChange = (e) => {
    setTicker(e.target.value);
    setLookupError(null);
  };

  const handleAmountChange = (e) => {
    const value = e.target.value;
    if (/^\d*\.?\d*$/.test(value)) {
      setAmount(value);
      setTradeError(null);
    }
  };

  const handleTrade = (e) => {
    e.preventDefault();
    if (!quote || !quote.current_price) {
      setTradeError("No live price available for this ticker right now");
      return;
    }
    if (!(Number(amount) > 0)) {
      setTradeError("Enter an amount greater than 0");
      return;
    }
    if (tradeType === "buy" && summary?.cash_balance != null) {
      const estimatedCost = Number(amount) * quote.current_price;
      if (estimatedCost > summary.cash_balance) {
        setTradeError(
          `This would cost about ${formatCurrency(estimatedCost)}, but you only have ${formatCurrency(summary.cash_balance)} available.`
        );
        return;
      }
    }
    if (tradeType === "sell") {
      const ownedAmount = ownedHolding ? Number(ownedHolding.amount) : 0;
      if (Number(amount) > ownedAmount) {
        setTradeError(`You only have ${ownedAmount} shares of ${historyTicker} available to sell.`);
        return;
      }
    }
    setTradeError(null);
    setSubmitting(true);

    fetch(`/api/stocks/${tradeType}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: historyTicker, amount: Number(amount) }),
    })
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.error || `${tradeType} failed (status ${res.status})`);
        return body;
      })
      .then(() => {
        setAmount("");
        performanceCacheRef.current.clear();
        fetchHoldings();
        fetchHistoryTransactions(historyTicker, activeHistoryRequestRef.current);
      })
      .catch((err) => setTradeError(err.message))
      .finally(() => setSubmitting(false));
  };

  const handleTickerLookupSubmit = (e) => {
    e.preventDefault();
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) return;
    if (!tickerLookup.has(symbol)) {
      setLookupError(`"${ticker}" isn't one of the companies from the search — pick one from the list.`);
      return;
    }
    setTicker("");
    setTickerResults([]);
    setLookupError(null);
    openHistory(symbol);
  };

  const handleFundSubmit = (e) => {
    e.preventDefault();
    if (!(Number(fundAmount) > 0)) {
      setFundError("Enter an amount greater than 0");
      return;
    }
    if (fundType === "withdraw" && summary?.cash_balance != null && Number(fundAmount) > summary.cash_balance) {
      setFundError(
      `You only have ${formatCurrency(summary.cash_balance)} available to withdraw.`
      );
      return;
      }
    setFundError(null);
    setFundSubmitting(true);

    fetch(`/api/accounts/${fundType}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: Number(fundAmount) }),
    })
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.error || `${fundType} failed (status ${res.status})`);
        return body;
      })
      .then(() => {
        setFundAmount("");
        fetchHoldings();
        fetchCashTransactions();
      })
      .catch((err) => setFundError(err.message))
      .finally(() => setFundSubmitting(false));
  };

  const fetchHistoryTransactions = (tickerSymbol, requestId) => {
    setHistoryLoading(true);
    setHistoryError(null);
    return fetch(`/api/transactions/?ticker=${encodeURIComponent(tickerSymbol)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (requestId === activeHistoryRequestRef.current) setHistoryTransactions(data);
      })
      .catch((err) => {
        if (requestId === activeHistoryRequestRef.current) setHistoryError(err.message);
      })
      .finally(() => {
        if (requestId === activeHistoryRequestRef.current) setHistoryLoading(false);
      });
  };

  const fetchQuote = (tickerSymbol, requestId) => {
    setQuote(null);
    setQuoteLoading(true);
    setQuoteError(null);
    return fetch(`/api/stocks/quote/${encodeURIComponent(tickerSymbol)}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.error || `Couldn't find "${tickerSymbol}"`);
        return body;
      })
      .then((data) => {
        if (requestId === activeHistoryRequestRef.current) setQuote(data);
      })
      .catch((err) => {
        if (requestId === activeHistoryRequestRef.current) setQuoteError(err.message);
      })
      .finally(() => {
        if (requestId === activeHistoryRequestRef.current) setQuoteLoading(false);
      });
  };

  const openHistory = (tickerSymbol) => {
    const requestId = (activeHistoryRequestRef.current += 1);
    setHistoryTicker(tickerSymbol);
    setHistoryTransactions([]);
    setHistoryPerformance([]);
    setHistoryPerformanceLoading(true);
    setTradeType("buy");
    setAmount("");
    setTradeError(null);

    fetchHistoryTransactions(tickerSymbol, requestId);
    fetchQuote(tickerSymbol, requestId);

    const { startDate, endDate } = getPerformanceDates("3M");
    fetch(`/api/stocks/performance/${encodeURIComponent(tickerSymbol)}?start_date=${startDate}&end_date=${endDate}`)
      .then((res) => (res.ok ? res.json() : { dates: [], equity: [] }))
      .then((data) => {
        if (requestId !== activeHistoryRequestRef.current) return;
        const dates = Array.isArray(data.dates) ? data.dates : [];
        const equity = Array.isArray(data.equity) ? data.equity : [];
        const chartData = dates
          .slice(0, equity.length)
          .map((date, index) => ({ date, value: Number(equity[index]) }))
          .filter((point) => Number.isFinite(point.value));
        setHistoryPerformance(chartData);
      })
      .catch(() => {
        if (requestId === activeHistoryRequestRef.current) setHistoryPerformance([]);
      })
      .finally(() => {
        if (requestId === activeHistoryRequestRef.current) setHistoryPerformanceLoading(false);
      });
  };

  const closeHistory = () => {
    setModalClosing(true);
    setTimeout(() => {
      setHistoryTicker(null);
      setHistoryTransactions([]);
      setHistoryError(null);
      setHistoryPerformance([]);
      setQuote(null);
      setQuoteError(null);
      setModalClosing(false);
    }, 180);
  };

  const closeRealizedModal = () => {
    setRealizedModalClosing(true);
    setTimeout(() => {
      setShowRealizedModal(false);
      setRealizedModalClosing(false);
    }, 180);
  };

  const fetchCashTransactions = () => {
    setCashTransactionsLoading(true);
    setCashTransactionsError(null);
    return fetch(`/api/accounts/transactions`)
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed: ${res.status}`);
        return res.json();
      })
      .then((data) => setCashTransactions(data))
      .catch((err) => setCashTransactionsError(err.message))
      .finally(() => setCashTransactionsLoading(false));
  };

  const openCashModal = () => {
    setShowCashModal(true);
    setFundType("deposit");
    setFundAmount("");
    setFundError(null);
    fetchCashTransactions();
  };

  const closeCashModal = () => {
    setCashModalClosing(true);
    setTimeout(() => {
      setShowCashModal(false);
      setCashModalClosing(false);
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
          <button
            type="button"
            className={`nav-link ${activeView === "overview" ? "active" : ""}`}
            aria-current={activeView === "overview" ? "page" : undefined}
            onClick={() => setActiveView("overview")}
          >
            Overview
          </button>

          <button
            type="button"
            className={`nav-link ${activeView === "performance" ? "active" : ""}`}
            aria-current={activeView === "performance" ? "page" : undefined}
            onClick={() => setActiveView("performance")}
          >
            Performance
          </button>

          <div className="avatar" aria-label="Eduardo profile">
            EP
          </div>
        </nav>
      </header>

      <main className="dashboard">
        {activeView === "overview" ? (
          <>
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

              <article
                className="summary-card clickable"
                onClick={openCashModal}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && openCashModal()}
              >
                <p className="summary-label">Cash available</p>
                {loading && !summary ? (
                  <p className="summary-value"><span className="skeleton-block" style={{ width: "90px", height: "22px" }} /></p>
                ) : (
                  <p className="summary-value">{formatCurrency(animatedCashBalance)}</p>
                )}
              </article>

              <article
                className="summary-card clickable"
                onClick={() => setShowRealizedModal(true)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setShowRealizedModal(true)}
              >
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
                        <th>% Portfolio</th>
                        <th>Unrealized P&amp;L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Array.from({ length: 5 }).map((_, i) => (
                        <tr key={i} className="skeleton-row" style={{ animationDelay: `${i * 60}ms` }}>
                          {Array.from({ length: 9 }).map((__, j) => (
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
                        <th>% Portfolio</th>
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
                          <td>
                            {holding.pct_of_portfolio != null ? `${holding.pct_of_portfolio.toFixed(2)}%` : "—"}
                          </td>
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

              <form className="trade-form" onSubmit={handleTickerLookupSubmit}>
                <h3>Look up a stock</h3>
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
                  <button type="submit" disabled={!ticker.trim()}>
                    View
                  </button>
                </div>
                {lookupError && <p className="error">{lookupError}</p>}
              </form>
            </section>

            {historyTicker && (
              <div className={`modal-overlay ${modalClosing ? "closing" : ""}`} onClick={closeHistory}>
                <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
                  <div className="modal-header">
                    <div>
                      <h3>{historyTicker}</h3>
                      <p>{quote?.company_name ?? tickerLookup.get(historyTicker) ?? "—"}</p>
                    </div>
                    <button type="button" className="modal-close" onClick={closeHistory} aria-label="Close">
                      &times;
                    </button>
                  </div>

                  <div className="modal-body">
                    {quoteLoading && (
                      <p className="quote-line">
                        <span className="skeleton-block" style={{ width: "140px", height: "22px" }} />
                      </p>
                    )}

                    {!quoteLoading && quoteError && (
                      <p className="error quote-line">Couldn't load a quote for {historyTicker}.</p>
                    )}

                    {!quoteLoading && !quoteError && quote && quote.current_price != null && (
                      <p className={`summary-value quote-line ${signClass(quote.day_change)}`}>
                        {formatCurrency(quote.current_price)}
                        <TrendArrow value={quote.day_change} />
                        <span className="summary-sub">
                          {formatCurrency(quote.day_change)} ({formatPercent(quote.day_change_pct)})
                        </span>
                      </p>
                    )}

                    {!quoteLoading && !quoteError && quote && quote.current_price == null && (
                      <p className="error quote-line">
                        Live price unavailable for {historyTicker} right now — trading is disabled.
                      </p>
                    )}

                    {historyPerformanceLoading && (
                      <div className="history-chart-skeleton" aria-label="Loading price history">
                        <span className="skeleton-block" style={{ width: "100%", height: "100%" }} />
                      </div>
                    )}

                    {!historyPerformanceLoading && historyPerformance.length > 1 && (
                      <div className="history-chart" aria-label={`${historyTicker} price, last 3 months`}>
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={historyPerformance} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                            <defs>
                              <linearGradient id="historyFill" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={CHART_ACCENT} stopOpacity={0.3} />
                                <stop offset="100%" stopColor={CHART_ACCENT} stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid stroke="rgba(255, 255, 255, 0.08)" vertical={false} />
                            <XAxis
                              dataKey="date"
                              axisLine={false}
                              tickLine={false}
                              minTickGap={40}
                              tick={{ fill: "rgba(238, 240, 248, 0.5)", fontSize: 11 }}
                              tickFormatter={(value) => formatChartDate(value)}
                            />
                            <YAxis
                              axisLine={false}
                              tickLine={false}
                              width={56}
                              domain={["auto", "auto"]}
                              tick={{ fill: "rgba(238, 240, 248, 0.5)", fontSize: 11 }}
                              tickFormatter={formatCompactCurrency}
                            />
                            <Tooltip
                              content={<PerformanceTooltip valueLabel={`${historyTicker} price`} />}
                              cursor={{ stroke: "rgba(238, 240, 248, 0.28)", strokeWidth: 1 }}
                            />
                            <Area
                              type="monotone"
                              dataKey="value"
                              stroke={CHART_ACCENT}
                              strokeWidth={2}
                              fill="url(#historyFill)"
                              activeDot={{ r: 4, fill: CHART_ACCENT, stroke: CHART_SURFACE, strokeWidth: 2 }}
                              animationDuration={500}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    )}

                    <form className="trade-form" onSubmit={handleTrade}>
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
                          disabled={!ownedHolding || Number(ownedHolding.amount) <= 0}
                          onClick={() => setTradeType("sell")}
                        >
                          Sell
                        </button>
                      </div>

                      <div className="trade-fields">
                        <input
                          type="text"
                          inputMode="decimal"
                          placeholder="Shares"
                          value={amount}
                          onChange={handleAmountChange}
                          required
                        />
                        <button type="submit" disabled={submitting || !quote?.current_price || !(Number(amount) > 0)}>
                          {submitting ? "Submitting..." : tradeType === "buy" ? "Buy" : "Sell"}
                        </button>
                      </div>

                      <p className="quote-estimate">
                        {Number(amount) > 0 && quote?.current_price != null
                          ? `Estimated ${tradeType === "buy" ? "cost" : "proceeds"}: ${formatCurrency(Number(amount) * quote.current_price)}`
                          : "Enter a share amount to see the estimated total"}
                      </p>

                      {ownedHolding && (
                        <p className="owned-line">
                          You own {Number(ownedHolding.amount)} shares · avg cost {formatCurrency(ownedHolding.avg_cost)}
                        </p>
                      )}

                      {tradeError && <p className="error">{tradeError}</p>}
                    </form>

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

            {showRealizedModal && (
              <div className={`modal-overlay ${realizedModalClosing ? "closing" : ""}`} onClick={closeRealizedModal}>
                <div className="modal-panel wide" onClick={(e) => e.stopPropagation()}>
                  <div className="modal-header">
                    <div>
                      <h3>Realized P&amp;L</h3>
                      <p>Profit or loss you've locked in by selling</p>
                    </div>
                    <button type="button" className="modal-close" onClick={closeRealizedModal} aria-label="Close">
                      &times;
                    </button>
                  </div>

                  <div className="modal-body">
                    {realizedLots.length === 0 && <p>No realized gains or losses yet — sell a position to see it here.</p>}

                    {realizedLots.length > 0 && (
                      <div className="table-wrapper">
                        <table>
                          <thead>
                            <tr>
                              <th>Date sold</th>
                              <th>Ticker</th>
                              <th>Shares</th>
                              <th>Avg cost</th>
                              <th>Sale price</th>
                              <th>Realized P&amp;L</th>
                            </tr>
                          </thead>
                          <tbody>
                            {realizedLots.map((lot, i) => (
                              <tr key={`${lot.ticker}-${lot.date}-${i}`}>
                                <td>{formatDate(lot.date)}</td>
                                <td><span className="ticker-badge">{lot.ticker}</span></td>
                                <td>{lot.shares}</td>
                                <td>{formatCurrency(lot.avg_cost)}</td>
                                <td>{formatCurrency(lot.sale_price)}</td>
                                <td className={signClass(lot.pnl)}>
                                  <span className="cell-with-icon">
                                    <TrendArrow value={lot.pnl} />
                                    {formatCurrency(lot.pnl)}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {showCashModal && (
              <div className={`modal-overlay ${cashModalClosing ? "closing" : ""}`} onClick={closeCashModal}>
                <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
                  <div className="modal-header">
                    <div>
                      <h3>Cash</h3>
                      <p>Deposit or withdraw, and see your history</p>
                    </div>
                    <button type="button" className="modal-close" onClick={closeCashModal} aria-label="Close">
                      &times;
                    </button>
                  </div>

                  <div className="modal-body">
                    <p className="summary-value quote-line">
                      {formatCurrency(summary?.cash_balance)}
                      <span className="summary-sub">available</span>
                    </p>

                    <form className="trade-form" onSubmit={handleFundSubmit}>
                      <div className="trade-toggle" data-active={fundType}>
                        <span className="trade-toggle-pill" aria-hidden="true" />
                        <button
                          type="button"
                          className={fundType === "deposit" ? "active" : ""}
                          onClick={() => setFundType("deposit")}
                        >
                          Deposit
                        </button>
                        <button
                          type="button"
                          className={fundType === "withdraw" ? "active" : ""}
                          onClick={() => setFundType("withdraw")}
                        >
                          Withdraw
                        </button>
                      </div>

                      <div className="trade-fields">
                        <input
                          type="text"
                          inputMode="decimal"
                          placeholder="Amount"
                          value={formatAmountForDisplay(fundAmount)}
                          onChange={makeAmountChangeHandler(setFundAmount, setFundError)}
                          required
                        />
                        <button type="submit" disabled={fundSubmitting || !(Number(fundAmount) > 0)}>
                          {fundSubmitting ? "Submitting..." : fundType === "deposit" ? "Deposit" : "Withdraw"}
                        </button>
                      </div>

                      {fundError && <p className="error">{fundError}</p>}
                    </form>

                    {cashTransactionsLoading && <p>Loading...</p>}
                    {cashTransactionsError && <p className="error">Failed to load history: {cashTransactionsError}</p>}

                    {!cashTransactionsLoading && !cashTransactionsError && cashTransactions.length === 0 && (
                      <p>No deposits or withdrawals yet.</p>
                    )}

                    {!cashTransactionsLoading && !cashTransactionsError && cashTransactions.length > 0 && (
                      <table>
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Type</th>
                            <th>Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[...cashTransactions]
                            .sort((a, b) => new Date(b.transaction_date) - new Date(a.transaction_date) || b.tr_id - a.tr_id)
                            .map((tx) => {
                              const isDeposit = tx.type === "deposit";
                              return (
                                <tr key={tx.tr_id}>
                                  <td>{formatDate(tx.transaction_date)}</td>
                                  <td className={isDeposit ? "positive" : "negative"}>{isDeposit ? "Deposit" : "Withdraw"}</td>
                                  <td>{formatCurrency(Math.abs(Number(tx.amount)))}</td>
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
          </>
        ) : (
          <section className="performance-view">
            <div className="performance-header">
              <div className="page-heading">
                <h1>Portfolio performance</h1>
                <p>Track how your total portfolio value has moved over time</p>
              </div>

              <div className="range-picker" aria-label="Performance date range">
                {PERFORMANCE_RANGES.map((range) => (
                  <button
                    key={range.label}
                    type="button"
                    className={performanceRange === range.label ? "active" : ""}
                    aria-pressed={performanceRange === range.label}
                    onClick={() => setPerformanceRange(range.label)}
                  >
                    {range.label}
                  </button>
                ))}
              </div>
            </div>

            <section className="performance-stats" aria-label="Performance summary">
              <article className="performance-hero">
                <p className="summary-label">Portfolio value</p>
                {performanceLoading && !performanceStats ? (
                  <span className="skeleton-block hero-skeleton" />
                ) : (
                  <p>{formatCurrency(performanceStats?.currentValue)}</p>
                )}
              </article>

              <article className="performance-stat">
                <p className="summary-label">{performanceRange} return</p>
                {performanceLoading && !performanceStats ? (
                  <span className="skeleton-block stat-skeleton" />
                ) : (
                  <p className={signClass(performanceStats?.change)}>
                    <TrendArrow value={performanceStats?.change} />
                    {formatCurrency(performanceStats?.change)}
                    {performanceStats?.changePct != null && (
                      <span>({formatPercent(performanceStats.changePct)})</span>
                    )}
                  </p>
                )}
              </article>

              <article className="performance-stat">
                <p className="summary-label">Best day</p>
                {performanceLoading && !performanceStats ? (
                  <span className="skeleton-block stat-skeleton" />
                ) : (
                  <>
                    <p className={signClass(performanceStats?.bestDay?.change)}>
                      <TrendArrow value={performanceStats?.bestDay?.change} />
                      {formatCurrency(performanceStats?.bestDay?.change)}
                    </p>
                    <span className="stat-caption">
                      {formatChartDate(performanceStats?.bestDay?.date, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                  </>
                )}
              </article>
            </section>

            <section className="performance-card">
              <div className="chart-heading">
                <div>
                  <h2>Portfolio value</h2>
                  <p>
                    {formatChartDate(performanceDateRange.startDate, {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}{" "}
                    —{" "}
                    {formatChartDate(performanceDateRange.endDate, {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </p>
                </div>
                {performanceLoading && performanceData.length > 0 && (
                  <span className="refresh-indicator">Updating…</span>
                )}
              </div>

              {performanceError && (
                <div className="chart-state" role="alert">
                  <span className="chart-state-icon">!</span>
                  <h3>Performance data is unavailable</h3>
                  <p>{performanceError}</p>
                  <button type="button" onClick={() => setPerformanceRequestKey((key) => key + 1)}>
                    Try again
                  </button>
                </div>
              )}

              {!performanceError && performanceLoading && performanceData.length === 0 && (
                <div className="chart-skeleton" aria-label="Loading performance chart">
                  <span className="skeleton-block chart-skeleton-line line-one" />
                  <span className="skeleton-block chart-skeleton-line line-two" />
                  <span className="skeleton-block chart-skeleton-line line-three" />
                </div>
              )}

              {!performanceError && !performanceLoading && performanceData.length === 0 && (
                <div className="chart-state">
                  <span className="chart-state-icon empty">↗</span>
                  <h3>No performance yet</h3>
                  <p>Buy your first position to start building a performance history.</p>
                </div>
              )}

              {!performanceError && performanceData.length > 0 && (
                <>
                  <div
                    className={`performance-chart ${performanceLoading ? "is-refreshing" : ""}`}
                    aria-label={`${performanceRange} portfolio value chart`}
                  >
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={performanceData}
                        margin={{ top: 12, right: 12, left: 4, bottom: 0 }}
                        accessibilityLayer
                      >
                        <defs>
                          <linearGradient id="performanceFill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={CHART_ACCENT} stopOpacity={0.3} />
                            <stop offset="100%" stopColor={CHART_ACCENT} stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="rgba(255, 255, 255, 0.08)" vertical={false} />
                        <XAxis
                          dataKey="date"
                          axisLine={false}
                          tickLine={false}
                          minTickGap={32}
                          tick={{ fill: "rgba(238, 240, 248, 0.5)", fontSize: 12 }}
                          tickFormatter={(value) => formatChartDate(value)}
                        />
                        <YAxis
                          axisLine={false}
                          tickLine={false}
                          width={68}
                          domain={["auto", "auto"]}
                          tick={{ fill: "rgba(238, 240, 248, 0.5)", fontSize: 12 }}
                          tickFormatter={formatCompactCurrency}
                        />
                        <Tooltip
                          content={<PerformanceTooltip />}
                          cursor={{ stroke: "rgba(238, 240, 248, 0.28)", strokeWidth: 1 }}
                        />
                        <Area
                          type="monotone"
                          dataKey="value"
                          stroke={CHART_ACCENT}
                          strokeWidth={2}
                          fill="url(#performanceFill)"
                          activeDot={{
                            r: 5,
                            fill: CHART_ACCENT,
                            stroke: CHART_SURFACE,
                            strokeWidth: 3,
                          }}
                          animationDuration={650}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>

                  <details className="performance-table">
                    <summary>View daily values</summary>
                    <div className="table-wrapper">
                      <table>
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Portfolio value</th>
                            <th>Daily change</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[...performanceData].reverse().map((point, index, reversedData) => {
                            const previousPoint = reversedData[index + 1];
                            const dailyChange = previousPoint ? point.value - previousPoint.value : null;
                            return (
                              <tr key={point.date}>
                                <td>{formatChartDate(point.date, {
                                  month: "short",
                                  day: "numeric",
                                  year: "numeric",
                                })}</td>
                                <td>{formatCurrency(point.value)}</td>
                                <td className={signClass(dailyChange)}>
                                  {dailyChange == null ? "—" : formatCurrency(dailyChange)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </details>
                </>
              )}
            </section>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
