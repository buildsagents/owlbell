// ───────────────────────────────────────────────────────────
// API Response/Request Types
// ───────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string | null;
  meta: ApiMeta | null;
}

export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string;
    details: Record<string, string[]> | null;
  };
}

export interface ApiMeta {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface PaginatedRequest {
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}
