import { ChangeDetectionStrategy, Component } from '@angular/core';
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
          <ion-label>My leagues</ion-label>
        </ion-tab-button>

        <ion-tab-button tab="discover" href="/tabs/discover">
          <ion-icon name="search-outline" aria-hidden="true" />
          <ion-label>Discover</ion-label>
        </ion-tab-button>

        <ion-tab-button tab="profile" href="/tabs/profile">
          <ion-icon name="person-circle-outline" aria-hidden="true" />
          <ion-label>Profile</ion-label>
        </ion-tab-button>
      </ion-tab-bar>
    </ion-tabs>
  `,
})
export class TabsPage {}
