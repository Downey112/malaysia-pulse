import { useEffect, useState } from "react";
import { api } from "./api";
import TrendChart from "./components/TrendChart";
import StateComparison from "./components/StateComparison";

const DEFAULT_DATASET = "cpi_state";
const DEFAULT_METRIC = "index_overall";
const DEFAULT_STATE = "selangor";

export default function App() {
  const [trend, setTrend] = useState([]);
  const [comparison, setComparison] = useState([]);
  const [states, setStates] = useState([]);
  const [selectedState, setSelectedState] = useState(DEFAULT_STATE);
  const [trendError, setTrendError] = useState(null);
  const [compareError, setCompareError] = useState(null);

  useEffect(() => {
    api.states().then((all) => setStates(all.filter((s) => s.state_code !== "malaysia")));

    api
      .compare(DEFAULT_DATASET, DEFAULT_METRIC)
      .then(setComparison)
      .catch((e) => setCompareError(e.message));
  }, []);

  useEffect(() => {
    setTrendError(null);
    api
      .indicators(DEFAULT_DATASET, DEFAULT_METRIC, selectedState)
      .then(setTrend)
      .catch((e) => setTrendError(e.message));
  }, [selectedState]);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Malaysia Pulse</h1>
      <p>State-level cost-of-living indicators, sourced live from data.gov.my.</p>

      <div style={{ marginBottom: "1.5rem" }}>
        <label htmlFor="state-picker" style={{ marginRight: "0.5rem", fontWeight: 500 }}>
          Viewing trend for:
        </label>
        <select
          id="state-picker"
          value={selectedState}
          onChange={(e) => setSelectedState(e.target.value)}
        >
          {states.map((s) => (
            <option key={s.state_code} value={s.state_code}>
              {s.state_name}
            </option>
          ))}
        </select>
      </div>

      {trendError && (
        <p style={{ color: "#a32d2d" }}>
          Trend error: {trendError}
        </p>
      )}

      <h2>CPI trend — {states.find((s) => s.state_code === selectedState)?.state_name ?? selectedState}</h2>
      <TrendChart data={trend} metric={DEFAULT_METRIC} />

      {compareError && (
        <p style={{ color: "#a32d2d" }}>
          Comparison error: {compareError}
        </p>
      )}

      <h2>By state (latest)</h2>
      <StateComparison data={comparison} metric={DEFAULT_METRIC} />
    </div>
  );
}
