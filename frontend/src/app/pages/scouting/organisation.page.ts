import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
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
import type { Organisation, ScoutingRole } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

@Component({
  selector: 'fm-scouting-organisation',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>{{ organisation()?.name ?? 'Organisation' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (organisation(); as org) {
        <p class="lede">
          {{ kindLabel(org.kind) }} · {{ org.scout_count }} scout(s). You are
          <strong>{{ org.my_role === 'scout_admin' ? 'a scout admin' : 'a scout' }}</strong> here.
        </p>

        <section class="fm-card section">
          <h3>Scouting team</h3>
          <ul class="list fm-stagger">
            @for (member of members(); track member.id) {
              <li class="list-row">
                <span class="avatar">{{ member.user_name.charAt(0) }}</span>
                <div class="grow">
                  <strong>{{ member.user_name }}</strong>
                  <small>{{ member.role === 'scout_admin' ? 'Scout admin' : 'Scout' }}</small>
                </div>
                @if (isAdmin()) {
                  <button type="button" class="btn danger small" [disabled]="busy()" (click)="remove(member)">Remove</button>
                }
              </li>
            }
          </ul>
        </section>

        @if (isAdmin()) {
          <form class="fm-card section" (submit)="add($event)">
            <h3>Add a scout</h3>
            <p class="hint">They need a Fair Measure account. Use the email they signed up with.</p>
            <label class="field">Email<input type="email" required [value]="email()" (input)="email.set($any($event.target).value)" /></label>
            <div class="segmented">
              <button type="button" [class.on]="role() === 'scout'" (click)="role.set('scout')">Scout</button>
              <button type="button" [class.on]="role() === 'scout_admin'" (click)="role.set('scout_admin')">Scout admin</button>
            </div>
            <div style="height: 12px"></div>
            <button type="submit" class="btn block" [disabled]="busy() || !email().includes('@')">Add to team</button>
          </form>
        }
      }
    </ion-content>
  `,
})
export class ScoutingOrganisationPage {
  private readonly scouting = inject(ScoutingService);
  private readonly route = inject(ActivatedRoute);
  private readonly toasts = inject(ToastController);

  readonly organisation = signal<Organisation | null>(null);
  readonly members = signal<ScoutingRole[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly email = signal('');
  readonly role = signal<'scout' | 'scout_admin'>('scout');
  readonly isAdmin = computed(() => this.organisation()?.my_role === 'scout_admin');

  private id = '';

  ionViewWillEnter(): void {
    this.id = this.route.snapshot.paramMap.get('id') ?? '';
    this.load();
  }

  private load(): void {
    this.scouting.organisations().subscribe((rows) => {
      this.organisation.set(rows.find((row) => row.id === this.id) ?? null);
      this.loading.set(false);
    });
    this.scouting.members(this.id).subscribe((rows) => this.members.set(rows));
  }

  add(event: Event): void {
    event.preventDefault();
    this.busy.set(true);
    this.scouting.addMember(this.id, this.email().trim(), this.role()).subscribe({
      next: async (member) => {
        this.busy.set(false);
        this.email.set('');
        await this.toast(`${member.user_name} added.`, 'success');
        this.load();
      },
      error: (err: unknown) => this.fail(err),
    });
  }

  remove(member: ScoutingRole): void {
    this.busy.set(true);
    this.scouting.removeMember(this.id, member.id).subscribe({
      next: () => {
        this.busy.set(false);
        this.load();
      },
      error: (err: unknown) => this.fail(err),
    });
  }

  kindLabel(kind: string): string {
    return { club: 'Club', academy: 'Academy', school: 'School', agency: 'Agency' }[kind] ?? kind;
  }

  private async fail(err: unknown): Promise<void> {
    this.busy.set(false);
    await this.toast(extractErrorMessage(err, 'That did not work.'), 'danger');
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
