import { bootstrapApplication } from '@angular/platform-browser';

import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

bootstrapApplication(AppComponent, appConfig)
  .then(() => {
    document.documentElement.classList.add('fm-booted');
  })
  .catch((error) => {
    console.error('Fair Measure failed to start', error);
    const show = (window as Window & { __fmShowBootError?: (message: string) => void })
      .__fmShowBootError;
    show?.(error instanceof Error ? error.message : 'The app failed to start.');
  });
