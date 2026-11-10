import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  ErrorHandler,
  provideZoneChangeDetection,
} from '@angular/core';
import {
  RouteReuseStrategy,
  provideRouter,
  withComponentInputBinding,
  withNavigationErrorHandler,
} from '@angular/router';
import { IonicRouteStrategy, provideIonicAngular } from '@ionic/angular/standalone';

import { routes } from './app.routes';
import { FairMeasureErrorHandler } from './core/app-error.handler';
import { authInterceptor } from './core/auth.interceptor';
import { reliabilityInterceptor } from './core/reliability.interceptor';
import { isStaleBuildError, reloadForNewBuild } from './core/stale-build';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideIonicAngular({ mode: 'ios', backButtonText: '' }),
    { provide: RouteReuseStrategy, useClass: IonicRouteStrategy },
    { provide: ErrorHandler, useClass: FairMeasureErrorHandler },
    provideRouter(
      routes,
      withComponentInputBinding(),
      withNavigationErrorHandler((navigation) => {
        if (isStaleBuildError(navigation.error)) reloadForNewBuild(navigation.url);
      }),
    ),
    provideHttpClient(withInterceptors([authInterceptor, reliabilityInterceptor])),
  ],
};
