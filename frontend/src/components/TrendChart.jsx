import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function TrendChart({ data, metric }) {
  if (!data || data.length === 0) {
    return <p>No data yet — run the ETL script first.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="obs_date" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="value" name={metric} stroke="#0f6e56" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}
