import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { IonIcon } from '@ionic/angular/standalone';

import type { ScoutReadiness } from '../core/scouting.models';

/** Shows whether a profile is complete enough for scouts, and what is still missing. */
@Component({
  selector: 'fm-scout-eligibility',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (readiness(); as r) {
      <div class="eligibility" [class.ok]="r.eligible" role="status">
        <div class="head">
          <ion-icon [name]="r.eligible ? 'shield-checkmark-outline' : 'alert-circle-outline'" aria-hidden="true" />
          <span class="grow">
            <strong>{{ r.eligible ? 'Scout-eligible' : 'Not yet eligible for scouts' }}</strong>
            <small>
              @if (r.eligible) {
                All {{ r.total }} profile fields are complete.
              } @else {
                {{ r.complete }} of {{ r.total }} profile fields complete. Scouts cannot see this profile until every field is filled in.
              }
            </small>
          </span>
          <span class="score">{{ percent() }}%</span>
        </div>
        <div class="bar" aria-hidden="true"><span [style.width.%]="percent()"></span></div>
        @if (!r.eligible) {
          @if (accountMissing().length) {
            <p class="group">
              <span>On your profile:</span>
              @for (item of accountMissing(); track item.key) {
                <em>{{ item.label }}</em>
              }
              @if (showActions()) {
                <button type="button" class="link" (click)="openAccount.emit()">Fill in</button>
              }
            </p>
          }
          @if (scoutingMissing().length) {
            <p class="group">
              <span>On your scouting profile:</span>
              @for (item of scoutingMissing(); track item.key) {
                <em>{{ item.label }}</em>
              }
              @if (showActions()) {
                <button type="button" class="link" (click)="openScouting.emit()">Fill in</button>
              }
            </p>
          }
        }
      </div>
    }
  `,
  styles: [
    `
      .eligibility {
        margin: 10px 0;
        padding: 12px;
        border-radius: 12px;
        border: 1px solid rgb(217 119 6 / 35%);
        background: rgb(245 158 11 / 10%);
      }

      .eligibility.ok {
        border-color: rgb(21 128 61 / 35%);
        background: rgb(34 197 94 / 10%);
      }

      .head {
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .head ion-icon {
        flex: 0 0 auto;
        font-size: 1.5rem;
        color: #d97706;
      }

      .ok .head ion-icon {
        color: #15803d;
      }

      .grow {
        flex: 1 1 auto;
        display: grid;
        gap: 2px;
      }

      small {
        color: var(--ion-color-medium);
      }

      .score {
        font-weight: 800;
        color: #b45309;
      }

      .ok .score {
        color: #15803d;
      }

      .bar {
        height: 6px;
        margin-top: 10px;
        border-radius: 999px;
        background: rgb(148 163 184 / 25%);
        overflow: hidden;
      }

      .bar span {
        display: block;
        height: 100%;
        border-radius: inherit;
        background: #d97706;
        transition: width 0.4s ease;
      }

      .ok .bar span {
        background: #15803d;
      }

      .group {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        margin: 10px 0 0;
        font-size: 0.82rem;
      }

      .group span {
        font-weight: 600;
      }

      .group em {
        padding: 2px 8px;
        border-radius: 999px;
        background: rgb(148 163 184 / 18%);
        font-style: normal;
      }

      .link {
        border: 0;
        background: none;
        padding: 0;
        color: var(--ion-color-primary);
        font-weight: 700;
        cursor: pointer;
      }
    `,
  ],
})
export class ScoutEligibilityComponent {
  readonly readiness = input<ScoutReadiness | null | undefined>(null);
  readonly showActions = input(true);
  readonly openAccount = output<void>();
  readonly openScouting = output<void>();

  readonly percent = computed(() => {
    const r = this.readiness();
    return r && r.total ? Math.round((r.complete / r.total) * 100) : 0;
  });
  readonly accountMissing = computed(() => (this.readiness()?.missing ?? []).filter((row) => row.section === 'account'));
  readonly scoutingMissing = computed(() =>
    (this.readiness()?.missing ?? []).filter((row) => row.section === 'scouting'),
  );
}
