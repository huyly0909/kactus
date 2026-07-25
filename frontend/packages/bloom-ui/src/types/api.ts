/** Standard API response envelope from kactus-fin backend */
export interface ApiResponse<T> {
    data: T;
    message: string;
    code: number;
}

/** Paginated response */
export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    pageSize: number;
    totalPages: number;
}

/** API error response */
export interface ApiError {
    code: number;
    message: string;
    detail?: string;
}
