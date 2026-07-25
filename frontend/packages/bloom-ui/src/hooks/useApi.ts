import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { UseQueryOptions, UseMutationOptions } from '@tanstack/react-query';
import { apiClient } from '../services/apiClient';
import type { ApiResponse } from '../types';
import type { AxiosRequestConfig } from 'axios';

/**
 * Generic GET hook using TanStack Query.
 * Auto-handles caching, background refresh, loading/error states.
 */
export const useApiQuery = <T>(
    queryKey: string[],
    url: string,
    config?: AxiosRequestConfig,
    options?: Omit<UseQueryOptions<ApiResponse<T>>, 'queryKey' | 'queryFn'>,
) => {
    return useQuery<ApiResponse<T>>({
        queryKey,
        queryFn: async () => {
            const { data } = await apiClient.get<ApiResponse<T>>(url, config);
            return data;
        },
        ...options,
    });
};

/**
 * Generic POST/PUT/DELETE mutation hook.
 * Automatically invalidates all queries on success.
 */
export const useApiMutation = <TData, TVariables>(
    url: string,
    method: 'post' | 'put' | 'patch' | 'delete' = 'post',
    options?: Omit<UseMutationOptions<ApiResponse<TData>, Error, TVariables>, 'mutationFn'>,
) => {
    const queryClient = useQueryClient();

    return useMutation<ApiResponse<TData>, Error, TVariables>({
        mutationFn: async (variables) => {
            let response;
            if (method === 'delete') {
                response = await apiClient.delete<ApiResponse<TData>>(url, { data: variables });
            } else if (method === 'patch') {
                response = await apiClient.patch<ApiResponse<TData>>(url, variables);
            } else if (method === 'put') {
                response = await apiClient.put<ApiResponse<TData>>(url, variables);
            } else {
                response = await apiClient.post<ApiResponse<TData>>(url, variables);
            }
            return response.data;
        },
        onSettled: () => {
            queryClient.invalidateQueries();
        },
        ...options,
    });
};
