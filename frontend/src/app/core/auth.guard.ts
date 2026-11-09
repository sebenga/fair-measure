import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated()) {
    return true;
  }
  // Remember where they were headed so login can send them back.
  return router.createUrlTree(['/login'], { queryParams: { next: state.url } });
};

export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return auth.isAuthenticated() ? router.createUrlTree(['/tabs/competitions']) : true;
};

/** Navigation state that opens the landing page for a signed-in user too. */
export const LANDING_STATE = { landing: true } as const;

export const landingGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  // Opening the app goes straight to the leagues; the home button asks for the landing page.
  const asked = router.getCurrentNavigation()?.extras.state?.['landing'] === true;
  return auth.isAuthenticated() && !asked ? router.createUrlTree(['/tabs/competitions']) : true;
};
