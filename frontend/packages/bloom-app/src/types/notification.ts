/** Notification feature types.
 *
 * Numeric ids arrive as strings (backend FancyInt → string in JSON). The
 * shared `NotificationChannel` model carries a per-platform `config` blob whose
 * secret fields come back masked as `***`. */

export type NotificationChannelType = 'telegram' | 'slack' | 'zalo_pa';
export type NotificationLevel = 'info' | 'warning' | 'critical';
export type NotificationLogStatus = 'success' | 'failed';
export type NotificationTrigger = 'manual' | 'event' | 'test';

export interface NotificationChannel {
  id: string;
  owner_id: string;
  name: string;
  channel_type: NotificationChannelType;
  is_active: boolean;
  config: Record<string, unknown>;
  last_used_at?: string | null;
}

/** Outcome of delivering one message to one conversation (fan-out channels). */
export interface DeliveryTarget {
  thread_id: string;
  thread_type: number;
  name?: string | null;
  ok: boolean;
  error?: string | null;
}

/** One *failed* transport attempt — the retry history behind `attempts`. */
export interface SendAttempt {
  attempt: number;
  error: string;
  at?: string | null;
}

export interface NotificationLog {
  id: string;
  channel_id: string;
  channel_type: NotificationChannelType;
  event_title: string;
  body?: string | null;
  level: NotificationLevel;
  status: NotificationLogStatus;
  trigger: NotificationTrigger;
  attempts: number;
  error?: string | null;
  /** Empty for single-target channels (Telegram/Slack). */
  targets: DeliveryTarget[];
  attempt_errors: SendAttempt[];
  delivered_count?: number | null;
  target_count?: number | null;
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

/** `getMe` — proves the token is live before a channel row is created. */
export interface TelegramBotInfo {
  id: string;
  username: string;
  first_name: string;
}

/** A chat the bot can see. `type` matters: a channel needs the bot as admin
 * with *Post messages*, a group does not. */
export interface TelegramChat {
  id: string;
  title: string;
  type: 'channel' | 'supergroup' | 'group' | 'private' | string;
  username?: string | null;
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

/** One saved conversation in a zalo_pa channel config (thread_type: 0=user, 1=group). */
export interface ZaloRecipientTarget {
  thread_id: string;
  thread_type: number;
  name?: string | null;
  avatar?: string | null;
}

/** Non-secret part of a zalo_pa channel config (secrets come back masked).
 * Legacy single-target rows still carry the scalar keys until re-saved. */
export interface ZaloPAConfig {
  recipients?: ZaloRecipientTarget[];
  zalo_user_id?: string | null;
  account_name?: string | null;
  /** @deprecated legacy single-target shape */
  thread_id?: string;
  thread_type?: number;
  recipient_name?: string | null;
}

export interface ZaloTestMessageResult {
  thread_id: string;
  thread_type: number;
  name?: string | null;
  ok: boolean;
  error?: string | null;
}

export interface ZaloTestMessageResponse {
  sent: number;
  failed: number;
  results: ZaloTestMessageResult[];
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
