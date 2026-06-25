import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { Clock } from "lucide-react";

const DAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

interface DaySchedule {
  dayOfWeek: number;
  isOpen: boolean;
  openTime: string;
  closeTime: string;
  is24Hours: boolean;
}

interface BusinessHoursProps {
  hours: DaySchedule[];
  onChange: (hours: DaySchedule[]) => void;
}

export function BusinessHours({ hours, onChange }: BusinessHoursProps) {
  const updateDay = (index: number, updates: Partial<DaySchedule>) => {
    const updated = [...hours];
    updated[index] = { ...updated[index], ...updates };
    onChange(updated);
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <Clock className="h-5 w-5 text-primary" />
          Business Hours
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {DAYS.map((day, index) => {
          const schedule = hours[index] || {
            dayOfWeek: index,
            isOpen: index > 0 && index < 6,
            openTime: "09:00",
            closeTime: "17:00",
            is24Hours: false,
          };

          return (
            <div
              key={day}
              className={cn(
                "flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between",
                schedule.isOpen ? "bg-card" : "bg-muted/30"
              )}
            >
              <div className="flex items-center gap-3">
                <Switch
                  checked={schedule.isOpen}
                  onCheckedChange={(checked) =>
                    updateDay(index, { isOpen: checked })
                  }
                />
                <span className="text-sm font-medium w-28">{day}</span>
              </div>

              {schedule.isOpen && (
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={schedule.is24Hours}
                      onChange={(e) =>
                        updateDay(index, { is24Hours: e.target.checked })
                      }
                      className="rounded border-gray-300"
                    />
                    <span className="text-xs">24h</span>
                  </label>

                  {!schedule.is24Hours && (
                    <div className="flex items-center gap-2">
                      <input
                        type="time"
                        value={schedule.openTime}
                        onChange={(e) =>
                          updateDay(index, { openTime: e.target.value })
                        }
                        className="rounded-md border bg-transparent px-2 py-1 text-sm"
                      />
                      <span className="text-muted-foreground">to</span>
                      <input
                        type="time"
                        value={schedule.closeTime}
                        onChange={(e) =>
                          updateDay(index, { closeTime: e.target.value })
                        }
                        className="rounded-md border bg-transparent px-2 py-1 text-sm"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
