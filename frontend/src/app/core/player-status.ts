import type { Availability, AvailabilityInfo } from './models';

/** A fantasy amount held in millions of rands, e.g. "R0", "R1.5m", "R100m". */
export function rands(millions: string | number | null | undefined): string {
  const value = Number(millions ?? 0);
  if (!Number.isFinite(value) || value === 0) return 'R0';
  const sign = value < 0 ? '-' : '';
  const size = Math.abs(value);
  return `${sign}R${Number.isInteger(size) ? size : size.toFixed(1)}m`;
}

/** "+R0.3m" or "-R0.1m" for a value move, or "" when it did not move. */
export function randsChange(millions: string | number | null | undefined): string {
  const value = Number(millions ?? 0);
  if (!Number.isFinite(value) || value === 0) return '';
  return value > 0 ? `+${rands(value)}` : rands(value);
}

export const AVAILABILITY_LABELS: Record<Availability, string> = {
  available: 'Available',
  injured: 'Injured',
  suspended: 'Suspended',
};

/** Two- or three-letter badge for a shirt: "INJ", "SUS", or "" when fit. */
export function availabilityTag(info: AvailabilityInfo): string {
  if (info.availability === 'injured') return 'INJ';
  if (info.availability === 'suspended') return 'SUS';
  return '';
}

export function isUnavailable(info: AvailabilityInfo): boolean {
  return !!info.availability && info.availability !== 'available';
}

/** "Injured · Hamstring · back 13 Nov", or "" when the player is available. */
export function availabilityText(info: AvailabilityInfo): string {
  if (!isUnavailable(info)) return '';
  const parts = [AVAILABILITY_LABELS[info.availability as Availability]];
  if (info.availability_note) parts.push(info.availability_note);
  if (info.available_from) {
    const back = new Date(`${info.available_from}T00:00:00`);
    if (!Number.isNaN(back.getTime())) {
      parts.push(`back ${back.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`);
    }
  }
  return parts.join(' · ');
}
