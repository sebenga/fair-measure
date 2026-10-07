import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/auth.guard';
import { competitionIdCanMatch } from './core/competition-id.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'tabs/competitions', pathMatch: 'full' },

  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./pages/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'register',
    canActivate: [guestGuard],
    loadComponent: () => import('./pages/register/register.page').then((m) => m.RegisterPage),
  },

  {
    path: 'tabs',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/tabs/tabs.page').then((m) => m.TabsPage),
    children: [
      { path: '', redirectTo: 'competitions', pathMatch: 'full' },
      {
        path: 'competitions/new',
        loadComponent: () =>
          import('./pages/competitions/competition-create.page').then(
            (m) => m.CompetitionCreatePage,
          ),
      },
      {
        path: 'competitions/:id/setup',
        loadComponent: () =>
          import('./pages/competitions/competition-setup.page').then(
            (m) => m.CompetitionSetupPage,
          ),
      },
      {
        path: 'competitions/:id/score',
        loadComponent: () =>
          import('./pages/competitions/competition-score.page').then(
            (m) => m.CompetitionScorePage,
          ),
      },
      {
        path: 'competitions/:competitionId/fixtures/:fixtureId',
        loadComponent: () =>
          import('./pages/fixtures/fixture-detail.page').then((m) => m.FixtureDetailPage),
      },
      {
        path: 'competitions/:id',
        canMatch: [competitionIdCanMatch],
        loadComponent: () =>
          import('./pages/competitions/competition-detail.page').then(
            (m) => m.CompetitionDetailPage,
          ),
      },
      {
        path: 'competitions',
        loadComponent: () =>
          import('./pages/competitions/competition-list.page').then(
            (m) => m.CompetitionListPage,
          ),
      },
      {
        path: 'discover',
        loadComponent: () =>
          import('./pages/discover/discover.page').then((m) => m.DiscoverPage),
      },
      {
        path: 'profile',
        loadComponent: () => import('./pages/profile/profile.page').then((m) => m.ProfilePage),
      },
    ],
  },

  // Older links land back inside the tab shell so the bottom nav stays up.
  { path: 'competitions/new', redirectTo: 'tabs/competitions/new', pathMatch: 'full' },
  { path: 'competitions/:id/setup', redirectTo: 'tabs/competitions/:id/setup' },
  { path: 'competitions/:id/score', redirectTo: 'tabs/competitions/:id/score' },
  {
    path: 'competitions/:competitionId/fixtures/:fixtureId',
    redirectTo: 'tabs/competitions/:competitionId/fixtures/:fixtureId',
  },
  { path: 'competitions/:id', redirectTo: 'tabs/competitions/:id' },

  { path: '**', redirectTo: 'tabs/competitions' },
];
