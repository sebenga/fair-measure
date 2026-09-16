import { Pipe, type PipeTransform } from '@angular/core';

const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;

@Pipe({ name: 'relativeTime', standalone: true })
export class RelativeTimePipe implements PipeTransform {
  transform(value: string | Date | null | undefined): string {
    if (!value) return '';

    const date = value instanceof Date ? value : new Date(value);
    const seconds = Math.round((Date.now() - date.getTime()) / 1000);

    if (seconds < 45) return 'just now';
    if (seconds < HOUR) return `${Math.round(seconds / MINUTE)}m`;
    if (seconds < DAY) return `${Math.round(seconds / HOUR)}h`;
    if (seconds < WEEK) return `${Math.round(seconds / DAY)}d`;

    return date.toLocaleDateString(undefined, {
      day: 'numeric',
      month: 'short',
      ...(date.getFullYear() === new Date().getFullYear() ? {} : { year: 'numeric' }),
    });
  }
}
