import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonFooter,
  IonHeader,
  IonSearchbar,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { CatalogSport } from '../../core/games.service';
import type { Preset } from '../../core/models';
import { GamesService } from '../../core/games.service';

@Component({
  selector: 'fm-games-sports',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonFooter, IonSearchbar, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './games.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button [defaultHref]="backHref()" /></ion-buttons>
        <ion-title>Add sports</ion-title>
      </ion-toolbar>
      <ion-toolbar>
        <ion-searchbar placeholder="Search sports or events" [debounce]="150" (ionInput)="query.set($any($event).detail.value ?? '')" />
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <div class="actions select-bar">
        <button type="button" class="btn ghost small" (click)="selectAll()">Select all</button>
        <button type="button" class="btn ghost small" (click)="selectSeason('summer')">Select all Summer</button>
        <button type="button" class="btn ghost small" (click)="selectSeason('winter')">Select all Winter</button>
        <button type="button" class="btn ghost small" (click)="clear()">Clear</button>
      </div>
      <p class="hint">
        Each event is created from its sport's locked preset and follows its International Federation's rules.
        Sports marked "Not available yet" have no locked preset in Fair Measure yet and are skipped.
      </p>

      <details class="fm-card section custom">
        <summary><strong>Add a custom event</strong> <small>A non-Olympic event from any preset, e.g. a sack race or netball</small></summary>
        <form (submit)="addCustom($event)">
          <div class="row">
            <label class="field">Sport<input [value]="customSport()" (input)="customSport.set($any($event.target).value)" placeholder="e.g. Netball" /></label>
            <label class="field">Event<input [value]="customName()" (input)="customName.set($any($event.target).value)" placeholder="e.g. Women's netball" /></label>
          </div>
          <div class="row">
            <label class="field">
              Rules (preset)
              <select (change)="customPreset.set($any($event.target).value)">
                <option value="">Choose</option>
                @for (preset of presets(); track preset.key) {
                  <option [value]="preset.key" [selected]="customPreset() === preset.key">{{ preset.label }}</option>
                }
              </select>
            </label>
            <label class="field">
              Entries
              <select (change)="customKind.set($any($event.target).value)">
                <option value="individual" [selected]="customKind() === 'individual'">Individual athletes</option>
                <option value="team" [selected]="customKind() === 'team'">One team per NOC</option>
              </select>
            </label>
          </div>
          <button type="submit" class="btn small" [disabled]="busy() || !customSport().trim() || !customName().trim() || !customPreset()">Add custom event</button>
        </form>
      </details>

      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else {
        @for (sport of visibleSports(); track sport.key) {
          <details class="fm-card section sport" [open]="!!query()">
            <summary>
              <input
                type="checkbox"
                [checked]="sportState(sport) === 'all'"
                [indeterminate]="sportState(sport) === 'some'"
                [disabled]="!sport.available"
                (click)="$event.stopPropagation()"
                (change)="toggleSport(sport, $any($event.target).checked)"
                [attr.aria-label]="'Select ' + sport.label"
              />
              <span class="grow">
                <strong>{{ sport.label }}</strong>
                <small>{{ sport.federation }} · {{ sport.season === 'summer' ? 'Summer' : 'Winter' }}{{ sport.note ? ' · ' + sport.note : '' }}</small>
              </span>
              @if (!sport.available) {
                <span class="badge warn">Not available yet</span>
              }
            </summary>
            @for (discipline of sport.disciplines; track discipline.name) {
              <p class="discipline">
                {{ discipline.name }}
                @if (!discipline.available) {
                  <span class="badge warn">Preset coming</span>
                }
              </p>
              <ul class="events">
                @for (event of discipline.events; track event.key) {
                  <li>
                    <label [class.disabled]="!event.available || event.added">
                      <input
                        type="checkbox"
                        [checked]="event.added || selected().has(event.key)"
                        [disabled]="!event.available || event.added"
                        (change)="toggle(event.key, $any($event.target).checked)"
                      />
                      {{ event.name }}
                      @if (event.added) {
                        <span class="badge ok">Added</span>
                      }
                    </label>
                  </li>
                }
              </ul>
            }
          </details>
        }
      }
      <div style="height: 32px"></div>
    </ion-content>

    <ion-footer>
      <ion-toolbar>
        <div class="footer">
          <span>{{ selected().size }} event(s) selected</span>
          <button type="button" class="btn" [disabled]="busy() || !selected().size" (click)="add()">
            Add {{ selected().size || '' }} event(s)
          </button>
        </div>
      </ion-toolbar>
    </ion-footer>
  `,
  styles: [
    `
      .select-bar {
        margin-top: 12px;
      }

      .custom summary {
        cursor: pointer;
      }

      .custom summary small {
        display: block;
        color: var(--ion-color-medium);
      }

      .custom form {
        margin-top: 10px;
      }

      .sport summary {
        display: flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;

        input {
          width: 20px;
          height: 20px;
        }

        .grow {
          flex: 1 1 auto;
          display: grid;

          small {
            color: var(--ion-color-medium);
            font-size: 0.78rem;
          }
        }
      }

      .discipline {
        margin: 12px 0 4px;
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }

      .events {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 4px 12px;
        margin: 0;
        padding: 0;
        list-style: none;

        label {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 4px 0;
          font-size: 0.9rem;
          cursor: pointer;

          &.disabled {
            color: var(--ion-color-medium);
            cursor: default;
          }
        }
      }

      .footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 6px 16px;
      }
    `,
  ],
})
export class GamesSportsPage {
  private readonly service = inject(GamesService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);
  private readonly api = inject(ApiService);

  readonly sports = signal<CatalogSport[]>([]);
  readonly presets = signal<Preset[]>([]);
  readonly customSport = signal('');
  readonly customName = signal('');
  readonly customPreset = signal('');
  readonly customKind = signal<'individual' | 'team'>('individual');
  readonly selected = signal<Set<string>>(new Set());
  readonly query = signal('');
  readonly loading = signal(true);
  readonly busy = signal(false);

  private readonly gamesId = computed(() => this.route.snapshot.paramMap.get('id') ?? '');
  readonly backHref = computed(() => `/tabs/games/${this.gamesId()}`);

  readonly visibleSports = computed(() => {
    const q = this.query().trim().toLowerCase();
    if (!q) return this.sports();
    return this.sports()
      .map((sport) => {
        if (sport.label.toLowerCase().includes(q)) return sport;
        const disciplines = sport.disciplines
          .map((discipline) => ({
            ...discipline,
            events: discipline.events.filter((event) => event.name.toLowerCase().includes(q)),
          }))
          .filter((discipline) => discipline.events.length || discipline.name.toLowerCase().includes(q));
        return disciplines.length ? { ...sport, disciplines } : null;
      })
      .filter((sport): sport is CatalogSport => sport !== null);
  });

  ionViewWillEnter(): void {
    this.load();
    this.api.listPresets().subscribe({
      next: (rows) =>
        this.presets.set(rows.filter((row) => row.key !== 'custom').sort((a, b) => a.label.localeCompare(b.label))),
    });
  }

  addCustom(event: Event): void {
    event.preventDefault();
    this.busy.set(true);
    this.service
      .addCustomEvent(this.gamesId(), {
        sport: this.customSport().trim(),
        name: this.customName().trim(),
        preset: this.customPreset(),
        kind: this.customKind(),
      })
      .subscribe({
        next: async (row) => {
          this.busy.set(false);
          this.customName.set('');
          const toast = await this.toasts.create({ message: `${row.sport}: ${row.name} added.`, color: 'success', duration: 2400, position: 'top' });
          await toast.present();
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          const toast = await this.toasts.create({
            message: extractErrorMessage(err, 'Could not add that event.'),
            color: 'danger',
            duration: 2600,
            position: 'top',
          });
          await toast.present();
        },
      });
  }

  private load(): void {
    this.service.catalog(this.gamesId()).subscribe({
      next: (sports) => {
        this.sports.set(sports);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  private openKeys(sport: CatalogSport): string[] {
    return sport.disciplines.flatMap((discipline) =>
      discipline.events.filter((event) => event.available && !event.added).map((event) => event.key),
    );
  }

  sportState(sport: CatalogSport): 'none' | 'some' | 'all' {
    const keys = this.openKeys(sport);
    if (!keys.length) return 'none';
    const chosen = keys.filter((key) => this.selected().has(key)).length;
    return chosen === 0 ? 'none' : chosen === keys.length ? 'all' : 'some';
  }

  toggle(key: string, on: boolean): void {
    this.selected.update((current) => {
      const next = new Set(current);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  toggleSport(sport: CatalogSport, on: boolean): void {
    for (const key of this.openKeys(sport)) this.toggle(key, on);
  }

  clear(): void {
    this.selected.set(new Set());
  }

  selectAll(): void {
    this.selected.set(new Set(this.sports().flatMap((sport) => this.openKeys(sport))));
  }

  selectSeason(season: 'summer' | 'winter'): void {
    this.selected.update(
      (current) =>
        new Set([
          ...current,
          ...this.sports()
            .filter((sport) => sport.season === season)
            .flatMap((sport) => this.openKeys(sport)),
        ]),
    );
  }

  add(): void {
    this.busy.set(true);
    this.service.addSports(this.gamesId(), { events: [...this.selected()] }).subscribe({
      next: async (result) => {
        this.busy.set(false);
        this.selected.set(new Set());
        const toast = await this.toasts.create({
          message: `${result.created.length} event(s) added${result.unavailable.length ? `, ${result.unavailable.length} not available yet` : ''}.`,
          color: 'success',
          duration: 2600,
          position: 'top',
        });
        await toast.present();
        void this.router.navigateByUrl(this.backHref());
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        const toast = await this.toasts.create({
          message: extractErrorMessage(err, 'Could not add those events.'),
          color: 'danger',
          duration: 2600,
          position: 'top',
        });
        await toast.present();
      },
    });
  }
}
