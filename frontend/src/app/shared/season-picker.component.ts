import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import type { Stage } from '../core/models';

/** Chips for a league's seasons, newest first, each old season labelled with its champion. */
@Component({
  selector: 'fm-season-picker',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="seasons" role="group" aria-label="Season">
      @for (season of newestFirst(); track season.id; let first = $first) {
        <button
          type="button"
          [class.on]="selected() === season.id"
          [attr.aria-pressed]="selected() === season.id"
          (click)="choose.emit(season.id)"
        >
          <strong>{{ season.name }}</strong>
          @if (season.champion) {
            <small>🏆 {{ season.champion }}</small>
          } @else if (first && !season.finished) {
            <small>Now</small>
          } @else if (season.finished) {
            <small>Finished</small>
          }
        </button>
      }
      @if (allowAll()) {
        <button
          type="button"
          [class.on]="selected() === null"
          [attr.aria-pressed]="selected() === null"
          (click)="choose.emit(null)"
        >
          <strong>All seasons</strong>
          <small>Combined</small>
        </button>
      }
    </div>
  `,
  styles: `
    :host {
      display: block;
      margin: 12px 0 0;
    }
    .seasons {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 2px 16px 4px;
      scrollbar-width: none;
    }
    .seasons::-webkit-scrollbar {
      display: none;
    }
    button {
      flex: 0 0 auto;
      display: grid;
      gap: 1px;
      min-width: 96px;
      max-width: 200px;
      padding: 7px 14px;
      border: 1px solid var(--fm-line, #e2e8f0);
      border-radius: 14px;
      background: var(--fm-surface, #fff);
      color: var(--fm-ink);
      font: inherit;
      text-align: left;
      cursor: pointer;
      transition:
        background-color 0.2s ease,
        color 0.2s ease;
    }
    strong {
      font-size: 0.86rem;
      font-weight: 800;
    }
    small {
      overflow: hidden;
      color: var(--ion-color-medium);
      font-size: 0.72rem;
      font-weight: 650;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    button.on {
      border-color: transparent;
      background: var(--fm-gradient);
      color: #fff;
    }
    button.on small {
      color: rgb(255 255 255 / 85%);
    }
  `,
})
export class SeasonPickerComponent {
  readonly seasons = input.required<Stage[]>();
  readonly selected = input<string | null>(null);
  readonly allowAll = input(false);
  readonly choose = output<string | null>();

  readonly newestFirst = computed(() => [...this.seasons()].reverse());
}
