// Set VITE_API_BASE_URL in a .env file locally, and as a build-time
// environment variable in your Azure Static Web Apps GitHub Actions workflow.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function get(path) {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`API request failed: ${path} (${res.status})`);
  }
  return res.json();
}

export const api = {
  states: () => get("/states"),
  datasets: () => get("/datasets"),
  metrics: (datasetId) => get(`/metrics?dataset_id=${encodeURIComponent(datasetId)}`),
  indicators: (datasetId, metric, stateCode = "malaysia") =>
    get(
      `/indicators?dataset_id=${encodeURIComponent(datasetId)}&metric=${encodeURIComponent(
        metric
      )}&state_code=${encodeURIComponent(stateCode)}`
    ),
  compare: (datasetId, metric) =>
    get(`/compare?dataset_id=${encodeURIComponent(datasetId)}&metric=${encodeURIComponent(metric)}`),
};
