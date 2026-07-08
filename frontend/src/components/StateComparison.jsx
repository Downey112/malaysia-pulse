import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function StateComparison({ data, metric }) {
  if (!data || data.length === 0) {
    return <p>No comparison data yet — run the ETL script first.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart data={data} layout="vertical" margin={{ top: 10, right: 20, left: 80, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" />
        <YAxis type="category" dataKey="state_name" width={120} />
        <Tooltip />
        <Bar dataKey="value" name={metric} fill="#378ADD" />
      </BarChart>
    </ResponsiveContainer>
  );
}
