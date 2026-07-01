import { useState } from "react";
import { useCalls } from "@/hooks/use-calls";
import { useCallStore } from "@/stores/call-store";
import { PageHeader } from "@/components/layout/PageHeader";
import { CallCard } from "@/components/calls/CallCard";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/use-debounce";
import { toTitleCase } from "@/lib/utils";
import type { CallStatus, CallDirection } from "@/types/call";
import { Search, X, Filter } from "lucide-react";

const STATUSES: CallStatus[] = ["ringing", "in_progress", "completed", "missed", "voicemail", "transferred", "failed"];
const DIRECTIONS: CallDirection[] = ["inbound", "outbound"];

export default function CallsListPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<CallStatus | null>(null);
  const [direction, setDirection] = useState<CallDirection | null>(null);
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounce(search, 300);

  const { data, isLoading, isError, refetch } = useCalls(
    { status, direction, search: debouncedSearch },
    { page, pageSize: 25 }
  );
  const activeCalls = useCallStore((s) => s.activeCalls);

  const hasFilters = status || direction || search;
  const clearFilters = () => {
    setStatus(null);
    setDirection(null);
    setSearch("");
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Calls" description="View and manage every handled call">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">{data?.pagination?.total ?? 0} total</span>
        </div>
      </PageHeader>

      {/* Active Calls Banner */}
      {activeCalls.length > 0 && (
        <div className="rounded-lg border border-success/20 bg-success/5 p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-success" />
            </span>
            <span className="text-sm font-semibold text-success">
              {activeCalls.length} active {activeCalls.length === 1 ? "call" : "calls"}
            </span>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {activeCalls.map((call) => (
              <CallCard key={call.id} call={call} compact />
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search calls..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2">
              <X className="h-4 w-4 text-muted-foreground" />
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={status || ""}
            onChange={(e) => setStatus((e.target.value as CallStatus) || null)}
            className="h-10 rounded-md border bg-transparent px-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">All Statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{toTitleCase(s)}</option>
            ))}
          </select>
          <select
            value={direction || ""}
            onChange={(e) => setDirection((e.target.value as CallDirection) || null)}
            className="h-10 rounded-md border bg-transparent px-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">All Directions</option>
            {DIRECTIONS.map((d) => (
              <option key={d} value={d}>{toTitleCase(d)}</option>
            ))}
          </select>
          {hasFilters && (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              <Filter className="mr-1 h-4 w-4" /> Clear
            </Button>
          )}
        </div>
      </div>

      {/* Call List */}
      {isLoading ? (
        <LoadingSpinner />
      ) : isError ? (
        <ErrorState onRetry={refetch} />
      ) : data?.calls && data.calls.length > 0 ? (
        <div className="space-y-2">
          {data.calls.map((call) => (
            <CallCard key={call.id} call={call} />
          ))}
        </div>
      ) : (
        <EmptyState
          title={hasFilters ? "No calls match filters" : "No calls yet"}
          description={hasFilters ? "Try adjusting your search or filters." : "Your call history will appear here once calls start coming in."}
          illustration="calls"
        >
          {hasFilters && (
            <Button variant="outline" onClick={clearFilters}>
              Clear Filters
            </Button>
          )}
        </EmptyState>
      )}

      {/* Pagination */}
      {data?.pagination && data.pagination.totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {data.pagination.totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(data.pagination.totalPages, p + 1))}
            disabled={page === data.pagination.totalPages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
