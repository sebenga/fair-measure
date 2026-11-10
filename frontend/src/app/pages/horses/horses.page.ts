import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type { Horse } from '../../core/results.models';
import { ResultsService } from '../../core/results.service';

type Draft = Pick<
  Horse,
  | 'name'
  | 'registration_number'
  | 'fei_id'
  | 'breed'
  | 'sex'
  | 'colour'
  | 'foaled_on'
  | 'owner_names'
  | 'trainer_name'
  | 'photo_url'
  | 'status'
>;

const EMPTY: Draft = {
  name: '',
  registration_number: '',
  fei_id: '',
  breed: '',
  sex: '',
  colour: '',
  foaled_on: null,
  owner_names: '',
  trainer_name: '',
  photo_url: '',
  status: 'active',
};

@Component({
  selector: 'fm-horses',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: '../scouting/scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/profile" /></ion-buttons>
        <ion-title>My horses</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <p class="lede">
        Preview — this tab is off in production until horse results ship. Register the horses you own,
        train or ride. A competition admin enters a horse with its rider; results are then kept for
        the horse, the rider and the trainer separately.
      </p>

      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else {
        <div class="fm-stagger">
          @for (horse of horses(); track horse.id) {
            <button type="button" class="fm-card card fm-lift" (click)="edit(horse)">
              <span class="avatar">
                @if (horse.photo_url) {
                  <img [src]="horse.photo_url" alt="" />
                } @else {
                  {{ horse.name.charAt(0) }}
                }
              </span>
              <span class="grow">
                <strong>{{ horse.name }}</strong>
                <small>
                  {{ details(horse) }}
                </small>
                <small>
                  {{ horse.registration_number || 'No registration number' }}{{ horse.trainer_label ? ' · trainer ' + horse.trainer_label : '' }}
                </small>
              </span>
              @if (horse.status === 'retired') {
                <span class="badge">Retired</span>
              }
              <ion-icon name="create-outline" aria-hidden="true" />
            </button>
          } @empty {
            <div class="fm-empty">
              <ion-icon name="ribbon-outline" aria-hidden="true" />
              <h3>No horses yet</h3>
              <p>Register your first horse below.</p>
            </div>
          }
        </div>
      }

      <form class="fm-card section" (submit)="save($event)">
        <h3>{{ editingId() ? 'Edit ' + (draft().name || 'horse') : 'Register a horse' }}</h3>
        <div class="row">
          <label class="field">Name<input required [value]="draft().name" (input)="set('name', $event)" /></label>
          <label class="field">Registration / passport no.<input [value]="draft().registration_number" (input)="set('registration_number', $event)" /></label>
        </div>
        <div class="row">
          <label class="field">FEI ID (optional)<input [value]="draft().fei_id" (input)="set('fei_id', $event)" /></label>
          <label class="field">Breed<input [value]="draft().breed" (input)="set('breed', $event)" /></label>
        </div>
        <div class="row">
          <label class="field">
            Sex
            <select (change)="set('sex', $event)">
              <option value="" [selected]="!draft().sex">Choose</option>
              @for (option of sexes; track option.key) {
                <option [value]="option.key" [selected]="draft().sex === option.key">{{ option.label }}</option>
              }
            </select>
          </label>
          <label class="field">Colour<input [value]="draft().colour" (input)="set('colour', $event)" /></label>
        </div>
        <div class="row">
          <label class="field">Foaled<input type="date" [value]="draft().foaled_on ?? ''" (input)="set('foaled_on', $event)" /></label>
          <label class="field">Trainer<input [value]="draft().trainer_name" (input)="set('trainer_name', $event)" /></label>
        </div>
        <label class="field">Owners not on Fair Measure<input [value]="draft().owner_names" (input)="set('owner_names', $event)" /></label>
        <label class="field">Photo link<input type="url" placeholder="https://" [value]="draft().photo_url" (input)="set('photo_url', $event)" /></label>
        @if (editingId()) {
          <label class="field">
            Status
            <select (change)="set('status', $event)">
              <option value="active" [selected]="draft().status === 'active'">Active</option>
              <option value="retired" [selected]="draft().status === 'retired'">Retired</option>
            </select>
          </label>
        }
        <div class="row">
          <button type="submit" class="btn block" [disabled]="busy() || !draft().name.trim()">
            {{ editingId() ? 'Save changes' : 'Register horse' }}
          </button>
          @if (editingId()) {
            <button type="button" class="btn ghost block" (click)="cancel()">Cancel</button>
          }
        </div>
      </form>
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .card {
        display: flex;
        align-items: center;
        gap: 12px;
        width: calc(100% - 32px);
        border: 0;
        text-align: left;
        font: inherit;
        color: var(--ion-text-color);
        cursor: pointer;
      }

      .grow {
        flex: 1 1 auto;
        min-width: 0;
        display: grid;
        gap: 2px;

        small {
          color: var(--ion-color-medium);
        }
      }
    `,
  ],
})
export class HorsesPage {
  private readonly results = inject(ResultsService);
  private readonly toasts = inject(ToastController);

  readonly sexes = [
    { key: 'mare', label: 'Mare' },
    { key: 'gelding', label: 'Gelding' },
    { key: 'stallion', label: 'Stallion' },
    { key: 'filly', label: 'Filly' },
    { key: 'colt', label: 'Colt' },
  ];
  readonly horses = signal<Horse[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly draft = signal<Draft>({ ...EMPTY });
  readonly editingId = signal<string | null>(null);

  ionViewWillEnter(): void {
    this.load();
  }

  private load(): void {
    this.results.horses().subscribe({
      next: (rows) => {
        this.horses.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  details(horse: Horse): string {
    return [horse.breed, this.sexLabel(horse.sex), horse.colour].filter(Boolean).join(' · ') || 'No details yet';
  }

  sexLabel(key: string): string {
    return this.sexes.find((option) => option.key === key)?.label ?? '';
  }

  set(field: keyof Draft, event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.draft.update((current) => ({ ...current, [field]: field === 'foaled_on' ? value || null : value }));
  }

  edit(horse: Horse): void {
    if (!horse.can_edit) return;
    this.editingId.set(horse.id);
    this.draft.set({
      name: horse.name,
      registration_number: horse.registration_number,
      fei_id: horse.fei_id,
      breed: horse.breed,
      sex: horse.sex,
      colour: horse.colour,
      foaled_on: horse.foaled_on,
      owner_names: horse.owner_names,
      trainer_name: horse.trainer_name,
      photo_url: horse.photo_url,
      status: horse.status,
    });
  }

  cancel(): void {
    this.editingId.set(null);
    this.draft.set({ ...EMPTY });
  }

  save(event: Event): void {
    event.preventDefault();
    if (this.busy()) return;
    this.busy.set(true);
    const id = this.editingId();
    const request = id ? this.results.updateHorse(id, this.draft()) : this.results.createHorse(this.draft());
    request.subscribe({
      next: async (horse) => {
        this.busy.set(false);
        this.cancel();
        this.load();
        await this.toast(id ? `${horse.name} saved.` : `${horse.name} registered.`, 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not save the horse.'), 'danger');
      },
    });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
