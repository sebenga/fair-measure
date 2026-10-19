import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type { CatalogItem, PhysicalTest, RecordablePlayers } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

/** Coach or official screen: record a physical test result for a player. */
@Component({
  selector: 'fm-record-test',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>Record a test result</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else {
        <form class="fm-card section" (submit)="save($event)">
          <label class="field">
            Player
            <select (change)="choosePlayer($any($event.target).value)">
              <option value="">Choose a player</option>
              @if (people()?.self; as me) {
                <option [value]="me.profile_id" [selected]="profileId() === me.profile_id">Me (self-reported)</option>
              }
              @for (row of people()?.players ?? []; track row.profile_id) {
                <option [value]="row.profile_id" [selected]="profileId() === row.profile_id">{{ row.name }}{{ row.team ? ' · ' + row.team : '' }}</option>
              }
            </select>
          </label>
          @if (!(people()?.players ?? []).length) {
            <p class="hint flush">Coaches see their team's players here; officials see the players in their competitions.</p>
          }

          @if (profileId()) {
            <label class="field">
              Sport
              <select (change)="chooseSport($any($event.target).value)">
                @for (item of sports(); track item.key) {
                  <option [value]="item.key" [selected]="sport() === item.key">{{ item.label }}</option>
                }
              </select>
            </label>
            <label class="field">
              Test
              <select (change)="testKey.set($any($event.target).value)">
                <option value="">Choose a test</option>
                @for (item of tests(); track item.key) {
                  <option [value]="item.key" [selected]="testKey() === item.key">{{ item.label }} ({{ item.unit }})</option>
                }
              </select>
            </label>
            @if (test(); as t) {
              <p class="hint flush">{{ t.description }} {{ t.better === 'lower' ? 'Lower is better.' : 'Higher is better.' }}</p>
              <div class="row">
                <label class="field">Result ({{ t.unit }})<input inputmode="decimal" [value]="value()" (input)="value.set($any($event.target).value)" placeholder="e.g. 5.42" /></label>
                <label class="field">Date<input type="date" [max]="today" [value]="date()" (input)="date.set($any($event.target).value)" /></label>
              </div>
              <label class="field">Venue<input [value]="venue()" (input)="venue.set($any($event.target).value)" placeholder="e.g. School field, timing gates" /></label>
              <div class="notice" [class.info]="!isSelf()">
                {{ isSelf() ? 'This result is labelled self-reported until a coach or official records it.' : 'You record this result as verified. Your name is shown with it.' }}
              </div>
              <button type="submit" class="btn block" [disabled]="busy() || !value().trim()">Save result</button>
            }
          }
        </form>
      }
    </ion-content>
  `,
  styles: [
    `
      .hint.flush {
        margin: 0 0 10px;
      }
      .notice {
        margin: 6px 0 12px;
      }
    `,
  ],
})
export class RecordTestPage {
  private readonly scouting = inject(ScoutingService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  readonly today = new Date().toISOString().slice(0, 10);
  readonly people = signal<RecordablePlayers | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly profileId = signal('');
  readonly sport = signal('');
  readonly tests = signal<PhysicalTest[]>([]);
  readonly testKey = signal('');
  readonly value = signal('');
  readonly date = signal(this.today);
  readonly venue = signal('');

  readonly isSelf = computed(() => this.people()?.self?.profile_id === this.profileId());
  readonly sports = computed<CatalogItem[]>(() => {
    const people = this.people();
    if (!people) return [];
    if (people.self?.profile_id === this.profileId()) return people.self.sports;
    return people.players.find((row) => row.profile_id === this.profileId())?.sports ?? [];
  });
  readonly test = computed(() => this.tests().find((row) => row.key === this.testKey()) ?? null);

  ionViewWillEnter(): void {
    this.scouting.recordablePlayers().subscribe({
      next: (people) => {
        this.people.set(people);
        this.loading.set(false);
        const query = this.route.snapshot.queryParamMap;
        const wanted = query.get('profile');
        if (wanted) {
          this.choosePlayer(wanted, query.get('sport') ?? '');
        }
      },
      error: () => this.loading.set(false),
    });
  }

  choosePlayer(profileId: string, sport = ''): void {
    this.profileId.set(profileId);
    const sports = this.sports();
    this.chooseSport(sports.find((item) => item.key === sport)?.key ?? sports[0]?.key ?? '');
  }

  chooseSport(sport: string): void {
    this.sport.set(sport);
    this.testKey.set('');
    this.tests.set([]);
    if (!sport) return;
    this.scouting.sportCatalogue(sport).subscribe({ next: (row) => this.tests.set(row.physical_tests) });
  }

  save(event: Event): void {
    event.preventDefault();
    const test = this.test();
    const value = Number(this.value().replace(',', '.'));
    if (!test || !Number.isFinite(value)) return;
    this.busy.set(true);
    this.scouting
      .recordTest(this.profileId(), {
        sport: this.sport(),
        test_key: test.key,
        value,
        tested_on: this.date(),
        venue: this.venue().trim(),
      })
      .subscribe({
        next: async (row) => {
          this.busy.set(false);
          this.value.set('');
          const toast = await this.toasts.create({
            message: `${row.test}: ${row.value} ${row.unit} saved (${row.label.toLowerCase()}).`,
            color: 'success',
            duration: 2600,
            position: 'top',
          });
          await toast.present();
          void this.router.navigate(['/tabs/scouting/players', this.profileId()], { queryParams: { tab: 'stats' } });
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          const toast = await this.toasts.create({
            message: extractErrorMessage(err, 'Could not save that result.'),
            color: 'danger',
            duration: 2600,
            position: 'top',
          });
          await toast.present();
        },
      });
  }
}
