import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AlertController, IonIcon, ToastController } from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { FixtureSide, ScrabbleBoard, ScrabbleMove, ScrabbleTile, ScrabbleWord } from '../../core/models';
import { RealtimeService } from '../../core/realtime.service';

interface DraftTile extends ScrabbleTile {
  id: string;
}

interface DraftWord {
  key: string;
  text: string;
  tiles: DraftTile[];
  dw: number;
  tw: number;
}

/** Live word-entry scorer: type a word, mark premiums and blanks, submit the official total. */
@Component({
  selector: 'fm-scrabble-scorer',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IonIcon],
  template: `
    @if (board(); as board) {
      <h3 class="fm-section-title">Word entry</h3>
      <p class="hint">
        Type the word. Tap a tile for DL/TL, long-press for a blank. Premiums apply only to new tiles.
        {{ board.tile_set.label }} tiles.
      </p>

      @if (canScore() && !kickoffBlocked()) {
        <div class="fm-card editor">
          <label class="field">
            Player
            <select [value]="sideId()" (change)="sideId.set(value($event))">
              @for (side of sides(); track side.id) {
                <option [value]="side.id">{{ side.participant.name }}</option>
              }
            </select>
          </label>

          @for (word of words(); track word.key) {
            <div class="word">
              <label class="field">
                {{ $first ? 'Word' : 'Cross word' }}
                <input
                  [value]="word.text"
                  maxlength="15"
                  autocomplete="off"
                  autocapitalize="characters"
                  (input)="setText(word.key, value($event))"
                />
              </label>
              <div class="rack" role="list">
                @for (tile of word.tiles; track tile.id) {
                  <button
                    type="button"
                    class="tile"
                    role="listitem"
                    [class.dl]="tile.letter_mult === 2 && !tile.blank && tile.new"
                    [class.tl]="tile.letter_mult === 3 && !tile.blank && tile.new"
                    [class.blank]="tile.blank"
                    [class.old]="!tile.new"
                    [attr.title]="tileHint(tile)"
                    (pointerdown)="pressStart(word.key, tile.id, $event)"
                    (pointerup)="pressEnd(word.key, tile.id)"
                    (pointerleave)="cancelPress()"
                  >
                    <b>{{ tile.letter }}</b>
                    <small>{{ tileValue(tile) }}</small>
                  </button>
                }
              </div>
              <div class="toggles">
                @for (tile of word.tiles; track tile.id) {
                  <button type="button" class="tiny" [class.on]="tile.new" (click)="toggleNew(word.key, tile.id)">
                    {{ tile.new ? 'new' : 'old' }}
                  </button>
                }
              </div>
              <div class="mults">
                <button type="button" [class.on]="word.dw === 0 && word.tw === 0" (click)="clearWordMult(word.key)">None</button>
                <button type="button" class="dw" [class.on]="word.dw > 0" (click)="cycleDw(word.key)">
                  DW{{ word.dw > 1 ? '×' + word.dw : '' }}
                </button>
                <button type="button" class="tw" [class.on]="word.tw > 0" (click)="cycleTw(word.key)">
                  TW{{ word.tw > 1 ? '×' + word.tw : '' }}
                </button>
                @if (!$first) {
                  <button type="button" class="ghost" (click)="removeWord(word.key)">Remove</button>
                }
              </div>
              @if (preview().words[$index]; as row) {
                <p class="break">{{ row.breakdown }}</p>
              }
            </div>
          }

          <div class="actions">
            <button type="button" class="ghost" (click)="addCross()">
              <ion-icon name="add-outline" aria-hidden="true" />
              Add cross word
            </button>
            <label class="bingo">
              <input type="checkbox" [checked]="bingo()" (change)="setBingo($any($event.target).checked)" />
              Bingo (all 7 tiles){{ autoBingo() && !overrodeBingo() ? ' · auto' : '' }}
            </label>
          </div>

          <p class="total">
            Move {{ preview().total }}
            @if (preview().bingo) {
              <em>+50 bingo</em>
            }
          </p>

          <div class="actions">
            <button type="button" class="primary" [disabled]="busy() || !mainWord()" (click)="submit('play')">
              Submit
            </button>
            <button type="button" class="ghost" [disabled]="busy()" (click)="submit('pass')">Pass</button>
            <button type="button" class="ghost" [disabled]="busy()" (click)="submit('exchange')">Exchange</button>
            <button type="button" class="ghost" [disabled]="busy()" (click)="submit('challenge_lost')">Lost challenge</button>
            @if (editingId()) {
              <button type="button" class="ghost" (click)="cancelEdit()">Cancel edit</button>
            }
          </div>
        </div>
      }

      <h3 class="fm-section-title">Turns</h3>
      <div class="fm-card history">
        @for (move of board.moves; track move.id) {
          <div class="turn">
            <strong>{{ move.player }}</strong>
            <span>{{ moveLabel(move) }}</span>
            <em>{{ move.total }}</em>
            @if (canScore()) {
              <button type="button" class="ghost" (click)="edit(move)">Edit</button>
              <button type="button" class="ghost" (click)="undo(move)">Undo</button>
            }
          </div>
        } @empty {
          <p class="hint">No turns yet.</p>
        }
      </div>

      @if (canScore() && !kickoffBlocked()) {
        <h3 class="fm-section-title">End of game</h3>
        <div class="fm-card racks">
          <p class="hint">Remaining tiles on each rack. Leave a rack empty if that player went out.</p>
          @for (side of sides(); track side.id) {
            <label class="field">
              {{ side.participant.name }}
              <input
                [value]="racks()[side.id] || ''"
                maxlength="7"
                autocapitalize="characters"
                placeholder="e.g. QST"
                (input)="setRack(side.id, value($event))"
              />
            </label>
          }
          <button type="button" class="primary" [disabled]="busy()" (click)="applyRacks()">Apply racks</button>
        </div>
      }
    }
  `,
  styles: [
    `
      .hint {
        margin: 0 16px 12px;
        font-size: 0.78rem;
        color: var(--ion-color-medium);
      }
      .editor,
      .history,
      .racks {
        display: grid;
        gap: 12px;
        margin: 0 16px 16px;
        padding: 14px;
      }
      .field {
        display: grid;
        gap: 4px;
        font-size: 0.75rem;
        font-weight: 650;
        color: var(--ion-color-medium);
      }
      .field input,
      .field select {
        min-height: 40px;
        padding: 6px 10px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 10px;
        background: var(--ion-background-color, #fff);
        color: inherit;
        font: inherit;
        text-transform: uppercase;
      }
      .word {
        display: grid;
        gap: 8px;
      }
      .rack {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .tile {
        position: relative;
        width: 44px;
        height: 48px;
        border: 0;
        border-radius: 8px;
        background: #f4e4b3;
        color: #1c1917;
        box-shadow: inset 0 0 0 1px #d6c089;
        cursor: pointer;
      }
      .tile b {
        font-size: 1.2rem;
        font-weight: 800;
      }
      .tile small {
        position: absolute;
        right: 4px;
        bottom: 3px;
        font-size: 0.62rem;
        font-weight: 800;
      }
      .tile.dl {
        background: #bfdbfe;
      }
      .tile.tl {
        background: #2563eb;
        color: #fff;
      }
      .tile.blank {
        background: #fff;
        font-style: italic;
        box-shadow: inset 0 0 0 2px #a8a29e;
      }
      .tile.old {
        opacity: 0.55;
      }
      .toggles {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
      }
      .tiny {
        min-width: 44px;
        padding: 2px 0;
        border: 0;
        border-radius: 6px;
        background: var(--ion-color-light);
        font-size: 0.62rem;
        font-weight: 700;
        text-transform: uppercase;
      }
      .tiny.on {
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }
      .mults,
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }
      .mults button,
      .actions button,
      .racks .primary {
        padding: 8px 12px;
        border: 0;
        border-radius: 999px;
        font: inherit;
        font-size: 0.78rem;
        font-weight: 700;
      }
      .dw.on {
        background: #f9a8d4;
      }
      .tw.on {
        background: #ef4444;
        color: #fff;
      }
      .primary {
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }
      .ghost,
      .mults button {
        background: var(--ion-color-light);
      }
      .bingo {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.8rem;
        font-weight: 650;
      }
      .break,
      .total {
        margin: 0;
        font-size: 0.82rem;
        font-weight: 650;
      }
      .total {
        font-size: 1.05rem;
      }
      .turn {
        display: grid;
        grid-template-columns: 1fr auto auto auto auto;
        gap: 8px;
        align-items: center;
        font-size: 0.85rem;
      }
      .turn em {
        font-style: normal;
        font-weight: 800;
      }
    `,
  ],
})
export class ScrabbleScorerComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);
  private readonly toasts = inject(ToastController);
  private readonly alerts = inject(AlertController);
  private readonly destroyRef = inject(DestroyRef);

  readonly competitionId = input.required<string>();
  readonly fixtureId = input.required<string>();
  readonly sides = input<FixtureSide[]>([]);
  readonly canScore = input(false);
  readonly kickoffBlocked = input(false);
  readonly changed = output<void>();

  readonly board = signal<ScrabbleBoard | null>(null);
  readonly busy = signal(false);
  readonly sideId = signal('');
  readonly words = signal<DraftWord[]>([emptyWord()]);
  readonly bingo = signal(false);
  readonly editingId = signal<string | null>(null);
  readonly racks = signal<Record<string, string>>({});
  private overrode = false;
  private press: ReturnType<typeof setTimeout> | null = null;
  private pressed = false;

  readonly autoBingo = computed(() => uniqueNew(this.words()) >= 7);
  readonly mainWord = computed(() => this.words()[0]?.text.trim().length > 0);
  readonly preview = computed(() => previewDraft(this.words(), this.bingo(), this.board()?.tile_set.values ?? {}));

  ngOnInit(): void {
    const first = this.sides()[0];
    if (first) this.sideId.set(first.id);
    this.load();
    this.realtime
      .onAny<{ fixture_id: string }>(['score.recorded', 'fixture.updated'])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((message) => {
        if (message.payload.fixture_id === this.fixtureId()) this.load();
      });
  }

  value(event: Event): string {
    return (event.target as HTMLInputElement | HTMLSelectElement).value;
  }

  overrodeBingo(): boolean {
    return this.overrode;
  }

  tileValue(tile: DraftTile): number {
    if (tile.blank) return 0;
    return this.board()?.tile_set.values[tile.letter] ?? 0;
  }

  tileHint(tile: DraftTile): string {
    if (tile.blank) return 'Blank · long-press to restore';
    if (!tile.new) return 'Already on the board';
    if (tile.letter_mult === 3) return 'Triple letter';
    if (tile.letter_mult === 2) return 'Double letter';
    return 'Tap for DL/TL · long-press for blank';
  }

  setText(key: string, text: string): void {
    const clean = text.toUpperCase().replace(/[^A-Z]/g, '');
    this.words.update((words) =>
      words.map((word) => {
        if (word.key !== key) return word;
        const tiles = [...clean].map((letter, index) => {
          const previous = word.tiles[index];
          return previous && previous.letter === letter
            ? previous
            : { id: `${key}-${index}-${letter}`, letter, blank: false, letter_mult: 1, new: true };
        });
        return { ...word, text: clean, tiles };
      }),
    );
    this.syncBingo();
  }

  pressStart(wordKey: string, tileId: string, event: PointerEvent): void {
    event.preventDefault();
    this.pressed = false;
    this.cancelPress();
    this.press = setTimeout(() => {
      this.pressed = true;
      this.toggleBlank(wordKey, tileId);
    }, 480);
  }

  pressEnd(wordKey: string, tileId: string): void {
    this.cancelPress();
    if (!this.pressed) this.cyclePremium(wordKey, tileId);
  }

  cancelPress(): void {
    if (this.press) clearTimeout(this.press);
    this.press = null;
  }

  cyclePremium(wordKey: string, tileId: string): void {
    this.patchTile(wordKey, tileId, (tile) => {
      if (tile.blank || !tile.new) return tile;
      const next = tile.letter_mult === 1 ? 2 : tile.letter_mult === 2 ? 3 : 1;
      return { ...tile, letter_mult: next };
    });
  }

  toggleBlank(wordKey: string, tileId: string): void {
    this.patchTile(wordKey, tileId, (tile) => ({ ...tile, blank: !tile.blank, letter_mult: 1 }));
  }

  toggleNew(wordKey: string, tileId: string): void {
    this.patchTile(wordKey, tileId, (tile) => ({ ...tile, new: !tile.new, letter_mult: tile.new ? 1 : tile.letter_mult }));
  }

  cycleDw(key: string): void {
    this.words.update((words) =>
      words.map((word) => (word.key === key ? { ...word, dw: word.dw === 2 ? 0 : word.dw + 1, tw: 0 } : word)),
    );
  }

  cycleTw(key: string): void {
    this.words.update((words) =>
      words.map((word) => (word.key === key ? { ...word, tw: word.tw === 2 ? 0 : word.tw + 1, dw: 0 } : word)),
    );
  }

  clearWordMult(key: string): void {
    this.words.update((words) => words.map((word) => (word.key === key ? { ...word, dw: 0, tw: 0 } : word)));
  }

  addCross(): void {
    this.words.update((words) => [...words, emptyWord()]);
    this.syncBingo();
  }

  removeWord(key: string): void {
    this.words.update((words) => words.filter((word) => word.key !== key));
    this.syncBingo();
  }

  setRack(sideId: string, letters: string): void {
    this.racks.update((racks) => ({ ...racks, [sideId]: letters.toUpperCase().replace(/[^A-Z?]/g, '') }));
  }

  moveLabel(move: ScrabbleMove): string {
    if (move.type === 'pass') return 'Pass';
    if (move.type === 'exchange') return 'Exchange';
    if (move.type === 'challenge_lost') return 'Lost challenge';
    const words = move.words.map((word) => word.text).join(' + ');
    return move.bingo ? `${words} · bingo` : words;
  }

  edit(move: ScrabbleMove): void {
    this.editingId.set(move.id);
    this.sideId.set(move.side);
    this.bingo.set(move.bingo);
    this.overrode = true;
    this.words.set(move.words.map((word) => fromSaved(word)));
  }

  cancelEdit(): void {
    this.editingId.set(null);
    this.words.set([emptyWord()]);
    this.bingo.set(false);
    this.overrode = false;
  }

  submit(type: ScrabbleMove['type']): void {
    if (this.busy()) return;
    if (type === 'play' && !this.mainWord()) {
      void this.toast('Type the word that was played.');
      return;
    }
    if (this.autoBingo() !== this.bingo()) this.overrode = true;
    const body: Record<string, unknown> = {
      side: this.sideId(),
      type,
      words: type === 'play' ? this.words().filter((word) => word.text).map(toSaved) : [],
      bingo: type === 'play' ? this.bingo() : false,
    };
    this.busy.set(true);
    const edit = this.editingId();
    const request = edit
      ? this.api.updateScrabbleMove(this.competitionId(), this.fixtureId(), edit, body)
      : this.api.recordScrabbleMove(this.competitionId(), this.fixtureId(), body);
    request.subscribe({
      next: (board) => {
        this.busy.set(false);
        this.board.set(board);
        this.cancelEdit();
        this.changed.emit();
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not record that turn.'));
      },
    });
  }

  async undo(move: ScrabbleMove): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Undo this turn?',
      message: `${move.player}: ${this.moveLabel(move)} (${move.total}).`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Undo',
          role: 'destructive',
          handler: () => {
            this.busy.set(true);
            this.api.deleteScrabbleMove(this.competitionId(), this.fixtureId(), move.id).subscribe({
              next: (board) => {
                this.busy.set(false);
                this.board.set(board);
                this.changed.emit();
              },
              error: async (err: unknown) => {
                this.busy.set(false);
                await this.toast(extractErrorMessage(err, 'Could not undo that turn.'));
              },
            });
          },
        },
      ],
    });
    await alert.present();
  }

  applyRacks(): void {
    const racks = this.sides().map((side) => ({ side: side.id, letters: this.racks()[side.id] ?? '' }));
    this.busy.set(true);
    this.api.applyScrabbleRacks(this.competitionId(), this.fixtureId(), { racks }).subscribe({
      next: (board) => {
        this.busy.set(false);
        this.board.set(board);
        this.changed.emit();
        void this.toast('Racks applied.', 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not apply the racks.'));
      },
    });
  }

  setBingo(on: boolean): void {
    this.overrode = true;
    this.bingo.set(on);
  }

  private syncBingo(): void {
    if (!this.overrode) this.bingo.set(uniqueNew(this.words()) >= 7);
  }

  private patchTile(wordKey: string, tileId: string, update: (tile: DraftTile) => DraftTile): void {
    this.words.update((words) =>
      words.map((word) =>
        word.key === wordKey ? { ...word, tiles: word.tiles.map((tile) => (tile.id === tileId ? update(tile) : tile)) } : word,
      ),
    );
    this.syncBingo();
  }

  private load(): void {
    this.api.getScrabbleBoard(this.competitionId(), this.fixtureId()).subscribe({
      next: (board) => {
        this.board.set(board);
        if (!this.sideId() && this.sides()[0]) this.sideId.set(this.sides()[0].id);
        this.bingo.set(this.overrode ? this.bingo() : this.autoBingo());
      },
    });
  }

  private async toast(message: string, color: 'danger' | 'success' = 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'bottom' });
    await toast.present();
  }
}

let wordSeq = 0;

function emptyWord(): DraftWord {
  wordSeq += 1;
  return { key: `w${wordSeq}`, text: '', tiles: [], dw: 0, tw: 0 };
}

function wordMult(word: DraftWord): number {
  if (word.dw) return 2 ** word.dw;
  if (word.tw) return 3 ** word.tw;
  return 1;
}

function fromSaved(word: ScrabbleWord): DraftWord {
  wordSeq += 1;
  const key = `w${wordSeq}`;
  const dw = word.word_mult === 4 ? 2 : word.word_mult === 2 ? 1 : 0;
  const tw = word.word_mult === 9 ? 2 : word.word_mult === 3 ? 1 : 0;
  return {
    key,
    text: word.text,
    dw,
    tw,
    tiles: word.tiles.map((tile, index) => ({
      ...tile,
      id: tile.id || `${key}-${index}`,
    })),
  };
}

function toSaved(word: DraftWord): ScrabbleWord {
  return {
    text: word.text,
    word_mult: wordMult(word),
    tiles: word.tiles.map((tile) => ({
      letter: tile.letter,
      blank: tile.blank,
      letter_mult: tile.letter_mult,
      new: tile.new,
      id: tile.id,
    })),
  };
}

function uniqueNew(words: DraftWord[]): number {
  const ids = new Set<string>();
  for (const word of words) {
    for (const tile of word.tiles) {
      if (tile.new) ids.add(tile.id);
    }
  }
  return ids.size;
}

function previewDraft(words: DraftWord[], bingo: boolean, values: Record<string, number>) {
  const rows = words
    .filter((word) => word.text)
    .map((word) => {
      let letterSum = 0;
      const parts: string[] = [];
      for (const tile of word.tiles) {
        const value = tile.blank ? 0 : (values[tile.letter] ?? 0);
        const mult = tile.blank || !tile.new ? 1 : tile.letter_mult;
        letterSum += value * mult;
        if (tile.blank) parts.push(`${tile.letter}(0)`);
        else if (mult > 1) parts.push(`${tile.letter}(${value}×${mult})`);
        else if (value !== 1) parts.push(`${tile.letter}(${value})`);
        else parts.push(tile.letter);
      }
      const mult = word.tiles.some((tile) => tile.new) ? wordMult(word) : 1;
      const total = letterSum * mult;
      const breakdown =
        mult > 1 ? `${parts.join(' + ')} = ${letterSum} × ${mult} = ${total}` : `${parts.join(' + ') || '0'} = ${letterSum}`;
      return { breakdown, total };
    });
  const subtotal = rows.reduce((sum, row) => sum + row.total, 0);
  const bonus = bingo ? 50 : 0;
  return { words: rows, bingo, total: subtotal + bonus };
}
