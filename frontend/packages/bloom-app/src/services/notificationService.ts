import { apiClient } from './apiClient';
import type { ApiResponse } from '@/types/api';
import type {
  NotificationChannel,
  NotificationChannelType,
  NotificationEvent,
  NotificationLog,
  ZaloCompleteResponse,
  ZaloQRGenerate,
  ZaloQRStatusResponse,
  ZaloRecipient,
} from '@/types/notification';

/** Backend pagination envelope (snake_case, matches kactus-common Pagination). */
interface ListEnvelope<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateChannelBody {
  name: string;
  channel_type: NotificationChannelType;
  config: Record<string, unknown>;
}

export interface UpdateChannelBody {
  name?: string;
  is_active?: boolean;
  config?: Record<string, unknown>;
}

const BASE = '/api/notifications';

export const notificationService = {
  list: async (): Promise<NotificationChannel[]> => {
    const { data } = await apiClient.get<ApiResponse<ListEnvelope<NotificationChannel>>>(BASE);
    return data.data.items;
  },

  get: async (id: string): Promise<NotificationChannel> => {
    const { data } = await apiClient.get<ApiResponse<NotificationChannel>>(`${BASE}/${id}`);
    return data.data;
  },

  create: async (body: CreateChannelBody): Promise<NotificationChannel> => {
    const { data } = await apiClient.post<ApiResponse<NotificationChannel>>(BASE, body);
    return data.data;
  },

  update: async (id: string, body: UpdateChannelBody): Promise<NotificationChannel> => {
    const { data } = await apiClient.put<ApiResponse<NotificationChannel>>(`${BASE}/${id}`, body);
    return data.data;
  },

  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`${BASE}/${id}`);
  },

  test: async (id: string): Promise<void> => {
    await apiClient.post(`${BASE}/${id}/test`);
  },

  send: async (id: string, event: NotificationEvent): Promise<void> => {
    await apiClient.post(`${BASE}/${id}/send`, event);
  },

  logs: async (id: string, limit = 50): Promise<NotificationLog[]> => {
    const { data } = await apiClient.get<ApiResponse<ListEnvelope<NotificationLog>>>(
      `${BASE}/${id}/logs`,
      { params: { limit } },
    );
    return data.data.items;
  },

  // ------------------------------------------------------- Zalo PA onboarding
  zaloPa: {
    generateQR: async (): Promise<ZaloQRGenerate> => {
      const { data } = await apiClient.post<ApiResponse<ZaloQRGenerate>>(
        `${BASE}/zalo-pa/qr/generate`,
      );
      return data.data;
    },

    waitForScan: async (sessionId: string): Promise<ZaloQRStatusResponse> => {
      const { data } = await apiClient.get<ApiResponse<ZaloQRStatusResponse>>(
        `${BASE}/zalo-pa/qr/${sessionId}/scan`,
      );
      return data.data;
    },

    waitForConfirm: async (sessionId: string): Promise<ZaloQRStatusResponse> => {
      const { data } = await apiClient.get<ApiResponse<ZaloQRStatusResponse>>(
        `${BASE}/zalo-pa/qr/${sessionId}/confirm`,
      );
      return data.data;
    },

    completeLogin: async (sessionId: string): Promise<ZaloCompleteResponse> => {
      const { data } = await apiClient.post<ApiResponse<ZaloCompleteResponse>>(
        `${BASE}/zalo-pa/qr/${sessionId}/complete`,
      );
      return data.data;
    },

    listRecipients: async (sessionId: string, query = ''): Promise<ZaloRecipient[]> => {
      const { data } = await apiClient.get<ApiResponse<ListEnvelope<ZaloRecipient>>>(
        `${BASE}/zalo-pa/sessions/${sessionId}/recipients`,
        { params: { query } },
      );
      return data.data.items;
    },

    createChannel: async (body: {
      session_id: string;
      name: string;
      thread_id: string;
      thread_type: number;
      recipient_name?: string;
    }): Promise<NotificationChannel> => {
      const { data } = await apiClient.post<ApiResponse<NotificationChannel>>(
        `${BASE}/zalo-pa/channels`,
        body,
      );
      return data.data;
    },

    reauth: async (channelId: string, sessionId: string): Promise<NotificationChannel> => {
      const { data } = await apiClient.put<ApiResponse<NotificationChannel>>(
        `${BASE}/zalo-pa/channels/${channelId}/reauth`,
        { session_id: sessionId },
      );
      return data.data;
    },
  },
};
