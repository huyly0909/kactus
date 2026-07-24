/** Notification feature types.
 *
 * Numeric ids arrive as strings (backend FancyInt → string in JSON). The
 * shared `NotificationChannel` model carries a per-platform `config` blob whose
 * secret fields come back masked as `***`. */

export type NotificationChannelType = 'telegram' | 'slack' | 'zalo_pa';
export type NotificationLevel = 'info' | 'warning' | 'critical';
export type NotificationLogStatus = 'success' | 'failed';
export type NotificationTrigger = 'manual' | 'event';

export interface NotificationChannel {
  id: string;
  owner_id: string;
  name: string;
  channel_type: NotificationChannelType;
  is_active: boolean;
  config: Record<string, unknown>;
  last_used_at?: string | null;
}

export interface NotificationLog {
  id: string;
  channel_id: string;
  channel_type: NotificationChannelType;
  event_title: string;
  level: NotificationLevel;
  status: NotificationLogStatus;
  trigger: NotificationTrigger;
  attempts: number;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

/** Per-type config shapes (secrets are write-only; reads come back masked). */
export interface TelegramConfig {
  bot_token: string;
  chat_id: string;
  parse_mode?: string;
}

export interface SlackConfig {
  webhook_url: string;
}

export interface NotificationEvent {
  title: string;
  body?: string;
  level?: NotificationLevel;
  fields?: [string, string][];
  url?: string;
}

// ----------------------------------------------------------- Zalo PA
export interface ZaloRecipient {
  id: string;
  name: string;
  avatar?: string | null;
  is_group: boolean;
}

export interface ZaloQRGenerate {
  session_id: string;
  code: string;
  image_url: string;
}

export type ZaloQRStatus = 'scanned' | 'confirmed' | 'refreshed' | 'expired' | 'rejected';

export interface ZaloQRStatusResponse {
  status: ZaloQRStatus;
  image_url?: string | null;
  code?: string | null;
  display_name?: string | null;
  avatar?: string | null;
}

export interface ZaloCompleteResponse {
  session_id: string;
  zalo_user_id: string;
  account_name?: string | null;
}
