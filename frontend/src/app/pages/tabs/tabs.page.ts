import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { AuthService } from '../../core/auth.service';
import {
  IonIcon,
  IonLabel,
  IonTabBar,
  IonTabButton,
  IonTabs,
} from '@ionic/angular/standalone';

@Component({
  selector: 'fm-tabs',
  standalone: true,
  imports: [IonTabs, IonTabBar, IonTabButton, IonIcon, IonLabel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-tabs>
      <ion-tab-bar slot="bottom">
        <ion-tab-button tab="competitions" href="/tabs/competitions">
          <ion-icon name="trophy-outline" aria-hidden="true" />
          <ion-label>{{ auth.isAuthenticated() ? 'My leagues' : 'Leagues' }}</ion-label>
        </ion-tab-button>

        @if (auth.isAuthenticated()) {
          <ion-tab-button tab="discover" href="/tabs/discover">
            <ion-icon name="search-outline" aria-hidden="true" />
            <ion-label>Discover</ion-label>
          </ion-tab-button>
          <ion-tab-button tab="scouting" href="/tabs/scouting">
            <ion-icon name="ribbon-outline" aria-hidden="true" />
            <ion-label>Scouting</ion-label>
          </ion-tab-button>
          <ion-tab-button tab="profile" href="/tabs/profile">
            <ion-icon name="person-circle-outline" aria-hidden="true" />
            <ion-label>Profile</ion-label>
          </ion-tab-button>
        } @else {
          <ion-tab-button tab="login" href="/login">
            <ion-icon name="person-circle-outline" aria-hidden="true" />
            <ion-label>Sign in</ion-label>
          </ion-tab-button>
        }
      </ion-tab-bar>
    </ion-tabs>
  `,
})
export class TabsPage {
  readonly auth = inject(AuthService);
}
