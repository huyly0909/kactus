/** Turn a cron job's structured fields into a sentence a human can act on.
 *
 * The server sends `cron` with wildcards already stripped (see
 * `kactus_data_plane.api.jobs._cron_fields`), so what arrives is only what
 * constrains the schedule — and a *missing* `day_of_week` is the signal that a
 * job runs every day, weekends included. That distinction is invisible in the
 * raw `cron[hour='8', minute='30']` string and is exactly what this exists for.
 *
 * Three shapes cover every job the scheduler registers; anything else falls
 * back to the raw trigger string rather than guessing.
 */

/** `Asia/Ho_Chi_Minh` → `GMT+7`. The cron fields are in this zone, not UTC, and
 * saying so is the whole point — a bare "15:35" invites the wrong reading. */
export function tzLabel(timezone?: string | null): string | null {
  if (!timezone) return null;
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      timeZoneName: 'shortOffset',
    }).formatToParts(new Date());
    return parts.find((p) => p.type === 'timeZoneName')?.value ?? null;
  } catch {
    return null; // unknown zone id — better silent than a wrong offset
  }
}

const pad = (v: string): string => v.padStart(2, '0');

/** True for a single numeric cron value (`"15"`); false for a range or step. */
const isSingle = (v: string | undefined): v is string => !!v && /^\d+$/.test(v);

export interface CadenceParts {
  /** i18n key under `scheduler.cadence.*`. */
  key: string;
  /** Interpolation values for that key. */
  values: Record<string, string>;
}

/**
 * Describe `cron` as an i18n key + values, or `null` when the shape is not one
 * we can phrase (caller then shows the raw `cadence`).
 */
export function describeCadence(
  cron: Record<string, string> | null | undefined,
  timezone?: string | null,
): CadenceParts | null {
  if (!cron) return null;
  const { day_of_week: dow, hour, minute } = cron;
  if (!hour || !isSingle(minute)) return null;

  const tz = tzLabel(timezone);
  const range = hour.match(/^(\d+)-(\d+)$/);

  if (range) {
    return {
      key: dow ? 'scheduler.cadence.hourly_range_days' : 'scheduler.cadence.hourly_range',
      values: {
        ...(dow ? { days: dow } : {}),
        from: `${pad(range[1] ?? '')}:00`,
        to: `${pad(range[2] ?? '')}:00`,
        minute: pad(minute),
        tz: tz ?? '',
      },
    };
  }

  if (!isSingle(hour)) return null;
  return {
    key: dow ? 'scheduler.cadence.daily_days' : 'scheduler.cadence.daily',
    values: {
      ...(dow ? { days: dow } : {}),
      at: `${pad(hour)}:${pad(minute)}`,
      tz: tz ?? '',
    },
  };
}
