import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export interface CelebratePiece {
  dx: number;
  dy: number;
  rot: number;
  delay: number;
  color: string;
}

export interface CelebrateMoment {
  title: string;
  pieces: CelebratePiece[];
}

/** Full-screen confetti banner used for goals and points milestones. */
@Component({
  selector: 'fm-celebrate-overlay',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (moment(); as m) {
      <div class="fm-celebrate" aria-live="polite">
        <div class="fm-celebrate-banner">{{ m.title }}</div>
        @for (piece of m.pieces; track $index) {
          <span
            class="fm-confetti"
            [style.--dx]="piece.dx + 'px'"
            [style.--dy]="piece.dy + 'px'"
            [style.--rot]="piece.rot + 'deg'"
            [style.--delay]="piece.delay + 'ms'"
            [style.background]="piece.color"
          ></span>
        }
      </div>
    }
  `,
})
export class CelebrateOverlayComponent {
  readonly moment = input<CelebrateMoment | null>(null);
}

const COLOURS = ['#f59e0b', '#14b8a6', '#2563eb', '#ec4899', '#22c55e', '#a855f7'];

/** Build a confetti burst for a celebration banner. */
export function buildCelebrateMoment(title: string, pieceCount = 42): CelebrateMoment {
  const pieces = Array.from({ length: pieceCount }, (_, index) => {
    const angle = (index / pieceCount) * Math.PI * 2 + Math.random() * 0.4;
    const reach = 140 + Math.random() * 220;
    return {
      dx: Math.round(Math.cos(angle) * reach),
      dy: Math.round(Math.sin(angle) * reach * 0.8 + 120),
      rot: Math.round(Math.random() * 720 - 360),
      delay: Math.round(Math.random() * 120),
      color: COLOURS[index % COLOURS.length],
    };
  });
  return { title, pieces };
}
