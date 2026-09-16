import { ChangeDetectionStrategy, Component, effect, inject } from '@angular/core';
import { IonApp, IonRouterOutlet } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  addOutline,
  alertCircle,
  alertCircleOutline,
  americanFootballOutline,
  basketballOutline,
  calendarOutline,
  chatbubbleOutline,
  chatbubblesOutline,
  chevronForwardOutline,
  close,
  closeCircleOutline,
  closeOutline,
  constructOutline,
  ellipse,
  ellipseOutline,
  ellipsisHorizontal,
  flagOutline,
  footballOutline,
  gitNetworkOutline,
  globeOutline,
  golfOutline,
  gridOutline,
  heart,
  heartOutline,
  imageOutline,
  lockClosedOutline,
  checkmarkOutline,
  optionsOutline,
  peopleOutline,
  personCircleOutline,
  pinOutline,
  podiumOutline,
  searchOutline,
  sendOutline,
  sparklesOutline,
  statsChartOutline,
  swapVerticalOutline,
  tennisballOutline,
  trashOutline,
  trophyOutline,
  videocam,
  waterOutline,
} from 'ionicons/icons';

import { AuthService } from './core/auth.service';
import { PushService } from './core/push.service';
import { RealtimeService } from './core/realtime.service';

@Component({
  selector: 'fm-root',
  standalone: true,
  imports: [IonApp, IonRouterOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-app>
      <ion-router-outlet />
    </ion-app>
  `,
})
export class AppComponent {
  private readonly auth = inject(AuthService);
  private readonly realtime = inject(RealtimeService);
  private readonly push = inject(PushService);

  constructor() {
    addIcons({
      addOutline,
      alertCircle,
      alertCircleOutline,
      americanFootballOutline,
      basketballOutline,
      calendarOutline,
      chatbubbleOutline,
      chatbubblesOutline,
      chevronForwardOutline,
      close,
      closeCircleOutline,
      closeOutline,
      constructOutline,
      ellipse,
      ellipseOutline,
      ellipsisHorizontal,
      flagOutline,
      footballOutline,
      gitNetworkOutline,
      globeOutline,
      golfOutline,
      gridOutline,
      heart,
      heartOutline,
      imageOutline,
      lockClosedOutline,
      checkmarkOutline,
      optionsOutline,
      peopleOutline,
      personCircleOutline,
      pinOutline,
      podiumOutline,
      searchOutline,
      sendOutline,
      sparklesOutline,
      statsChartOutline,
      swapVerticalOutline,
      tennisballOutline,
      trashOutline,
      trophyOutline,
      videocam,
      waterOutline,
    });

    // Hold one socket for the whole session, tied to being signed in.
    effect(() => {
      if (this.auth.isAuthenticated()) {
        this.realtime.connect();
        void this.push.syncOnStartup();
      } else {
        this.realtime.disconnect();
      }
    });
  }
}
