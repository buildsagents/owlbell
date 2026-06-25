import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DailyCallData } from "@/types/analytics";
import { formatDate } from "@/lib/utils";

interface CallVolumeChartProps {
  data: DailyCallData[];
}

export function CallVolumeChart({ data }: CallVolumeChartProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Call Volume</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorAnswered" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#059669" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#059669" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorMissed" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#e11d48" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#e11d48" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="date"
              tickFormatter={(val) => formatDate(val, "MMM d")}
              tick={{ fontSize: 12 }}
              stroke="#94a3b8"
            />
            <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
            <Tooltip
              formatter={(value: number, name: string) => [value, name === "answered" ? "Answered" : "Missed"]}
              labelFormatter={(label) => formatDate(label as string, "MMM d, yyyy")}
              contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0" }}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="answered"
              stroke="#059669"
              fillOpacity={1}
              fill="url(#colorAnswered)"
              name="Answered"
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="missed"
              stroke="#e11d48"
              fillOpacity={1}
              fill="url(#colorMissed)"
              name="Missed"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
