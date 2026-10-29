import { ChangeDetectionStrategy, Component, effect, inject } from '@angular/core';
import { IonApp, IonRouterOutlet } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  trendingUpOutline,
  notificationsOffOutline,
  listOutline,
  mailOutline,
  cloudUploadOutline,
  cloudDoneOutline,
  qrCodeOutline,
  starOutline,
  notifications,
  notificationsOutline,
  downloadOutline,
  radioOutline,
  timeOutline,
  addOutline,
  alertCircle,
  alertCircleOutline,
  americanFootballOutline,
  baseballOutline,
  basketballOutline,
  bookOutline,
  calendarOutline,
  chatbubbleOutline,
  chatbubblesOutline,
  chevronForwardOutline,
  close,
  closeCircleOutline,
  closeOutline,
  constructOutline,
  createOutline,
  diceOutline,
  discOutline,
  ellipse,
  ellipseOutline,
  eyeOffOutline,
  eyeOutline,
  extensionPuzzleOutline,
  ellipsisHorizontal,
  fitnessOutline,
  flagOutline,
  flashOutline,
  footballOutline,
  gitMergeOutline,
  gitNetworkOutline,
  globeOutline,
  golfOutline,
  gridOutline,
  heart,
  heartOutline,
  helpCircleOutline,
  imageOutline,
  locateOutline,
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
  stopwatchOutline,
  swapVerticalOutline,
  tennisballOutline,
  trashOutline,
  trophyOutline,
  videocam,
  waterOutline,
  businessOutline,
  clipboardOutline,
  personOutline,
  ribbonOutline,
  shieldCheckmarkOutline,
  documentTextOutline,
  printOutline,
  shirtOutline,
  lockOpenOutline,
  refreshOutline,
  removeCircleOutline,
  addCircleOutline,
  megaphoneOutline,
  arrowUndoOutline,
  cardOutline,
  videocamOutline,
  textOutline,
  banOutline,
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
      <div id="fm-runtime-error" hidden>
        <span>Something went wrong on this screen.</span>
        <span id="fm-runtime-error-detail"></span>
        <button type="button" (click)="reload()">Reload</button>
      </div>
      <ion-router-outlet />
    </ion-app>
  `,
  styles: [
    `
      #fm-runtime-error {
        position: sticky;
        top: 0;
        z-index: 1000;
        display: flex;
        gap: 12px;
        align-items: center;
        justify-content: center;
        padding: 10px 16px;
        background: #b45309;
        color: #fff;
        font-size: 0.9rem;
      }
      #fm-runtime-error[hidden] {
        display: none;
      }
      #fm-runtime-error button {
        border: 0;
        border-radius: 8px;
        padding: 6px 10px;
        background: #fff;
        color: #9a3412;
        font: inherit;
        font-weight: 600;
      }
    `,
  ],
})
export class AppComponent {
  private readonly auth = inject(AuthService);
  private readonly realtime = inject(RealtimeService);
  private readonly push = inject(PushService);

  constructor() {
    addIcons({
      trendingUpOutline,
      notificationsOffOutline,
      listOutline,
      mailOutline,
      cloudUploadOutline,
      cloudDoneOutline,
      qrCodeOutline,
      starOutline,
      notifications,
      notificationsOutline,
      downloadOutline,
      radioOutline,
      timeOutline,
      businessOutline,
      clipboardOutline,
      personOutline,
      ribbonOutline,
      shieldCheckmarkOutline,
      addOutline,
      alertCircle,
      alertCircleOutline,
      americanFootballOutline,
      baseballOutline,
      basketballOutline,
      bookOutline,
      calendarOutline,
      chatbubbleOutline,
      chatbubblesOutline,
      chevronForwardOutline,
      close,
      closeCircleOutline,
      closeOutline,
      constructOutline,
      createOutline,
      diceOutline,
      discOutline,
      ellipse,
      ellipseOutline,
      eyeOffOutline,
      eyeOutline,
      extensionPuzzleOutline,
      ellipsisHorizontal,
      fitnessOutline,
      flagOutline,
      flashOutline,
      footballOutline,
      gitMergeOutline,
  gitNetworkOutline,
      globeOutline,
      golfOutline,
      gridOutline,
      heart,
      heartOutline,
      helpCircleOutline,
      imageOutline,
      locateOutline,
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
      stopwatchOutline,
      swapVerticalOutline,
      tennisballOutline,
      trashOutline,
      trophyOutline,
      documentTextOutline,
      printOutline,
      cardOutline,
      videocamOutline,
      shirtOutline,
      lockOpenOutline,
      refreshOutline,
      removeCircleOutline,
      addCircleOutline,
      megaphoneOutline,
      arrowUndoOutline,
      videocam,
      waterOutline,
      textOutline,
      banOutline,
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

  reload(): void {
    window.location.reload();
  }
}
