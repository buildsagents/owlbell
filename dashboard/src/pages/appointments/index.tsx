import { useState } from "react";
import { useAppointments } from "@/hooks/use-appointments";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { startOfMonth, endOfMonth, format, addMonths, subMonths, eachDayOfInterval, isSameDay, isToday } from "date-fns";
import { CalendarDays, ChevronLeft, ChevronRight, Clock, MapPin, Phone } from "lucide-react";

export default function AppointmentsPage() {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [view, setView] = useState<"month" | "list">("month");

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const { data: appointments, isLoading } = useAppointments(
    format(monthStart, "yyyy-MM-dd"),
    format(monthEnd, "yyyy-MM-dd")
  );

  const days = eachDayOfInterval({ start: monthStart, end: monthEnd });

  const statusColors: Record<string, string> = {
    scheduled: "bg-info/10 text-info",
    confirmed: "bg-success/10 text-success",
    completed: "bg-muted text-muted-foreground",
    cancelled: "bg-destructive/10 text-destructive",
    no_show: "bg-warning/10 text-warning",
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Appointments" description="Booked appointments and availability">
        <div className="flex gap-2">
          <Button variant={view === "month" ? "default" : "outline"} size="sm" onClick={() => setView("month")}>
            <CalendarDays className="mr-1 h-4 w-4" /> Month
          </Button>
          <Button variant={view === "list" ? "default" : "outline"} size="sm" onClick={() => setView("list")}>
            List
          </Button>
        </div>
      </PageHeader>

      {view === "month" ? (
        <>
          <div className="flex items-center justify-between">
            <Button variant="outline" size="sm" onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <h2 className="text-lg font-semibold">{format(currentMonth, "MMMM yyyy")}</h2>
            <Button variant="outline" size="sm" onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>

          <div className="grid grid-cols-7 gap-1">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
              <div key={d} className="p-2 text-center text-xs font-semibold text-muted-foreground">{d}</div>
            ))}
            {days.map((day) => {
              const dayAppts = appointments?.filter((a) => isSameDay(new Date(a.scheduledAt), day)) || [];
              return (
                <div
                  key={day.toISOString()}
                  className={cn(
                    "min-h-[80px] rounded-lg border p-2 transition-colors",
                    isToday(day) ? "border-primary bg-primary/5" : "hover:bg-accent"
                  )}
                >
                  <span className={cn("text-sm font-medium", isToday(day) && "text-primary")}>
                    {format(day, "d")}
                  </span>
                  <div className="mt-1 space-y-1">
                    {dayAppts.slice(0, 2).map((a) => (
                      <div key={a.id} className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium truncate", statusColors[a.status])}>
                        {format(new Date(a.scheduledAt), "h:mm a")} {a.customerName}
                      </div>
                    ))}
                    {dayAppts.length > 2 && (
                      <p className="text-[10px] text-muted-foreground">+{dayAppts.length - 2} more</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <div className="space-y-2">
          {isLoading ? <LoadingSpinner /> : appointments && appointments.length > 0 ? (
            appointments.map((appt) => (
              <div key={appt.id} className="flex items-center gap-4 rounded-lg border bg-card p-4">
                <div className="flex h-12 w-12 flex-col items-center justify-center rounded-lg bg-primary/10">
                  <span className="text-xs font-semibold text-primary">{format(new Date(appt.scheduledAt), "MMM")}</span>
                  <span className="text-lg font-bold leading-none text-primary">{format(new Date(appt.scheduledAt), "d")}</span>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{appt.title}</span>
                    <Badge className={statusColors[appt.status]}>{appt.status}</Badge>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {format(new Date(appt.scheduledAt), "h:mm a")}</span>
                    <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> {appt.customerPhone}</span>
                    {appt.location && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {appt.location}</span>}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <EmptyState title="No appointments" description="Booked appointments will appear here." illustration="appointments" />
          )}
        </div>
      )}
    </div>
  );
}
