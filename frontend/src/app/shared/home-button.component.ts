import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router } from '@angular/router';
import { IonButton, IonIcon, NavController } from '@ionic/angular/standalone';
import { filter, map } from 'rxjs';

import { LANDING_STATE } from '../core/auth.guard';

/** Back to the landing page from anywhere, signed in or not. */
@Component({
  selector: 'fm-home-button',
  standalone: true,
  imports: [IonButton, IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (!atHome()) {
      <ion-button class="home" (click)="goHome()" aria-label="Back to the landing page" title="Home">
        <ion-icon slot="icon-only" name="home-outline" aria-hidden="true" />
      </ion-button>
    }
  `,
  styles: [
    `
      :host {
        display: contents;
      }
    `,
  ],
})
export class HomeButtonComponent {
  private readonly router = inject(Router);
  private readonly nav = inject(NavController);

  private readonly url = toSignal(
    this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd),
      map((event) => event.urlAfterRedirects),
    ),
    { initialValue: this.router.url },
  );

  readonly atHome = computed(() => (this.url() || '/').split(/[?#]/)[0] === '/');

  goHome(): void {
    void this.nav.navigateRoot('/', { animationDirection: 'back', state: LANDING_STATE });
  }
}
