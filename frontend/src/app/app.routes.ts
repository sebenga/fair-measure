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
        path: 'competitions',
        loadComponent: () =>
          import('./pages/competitions/competition-list.page').then(
            (m) => m.CompetitionListPage,
          ),
      },
      {
        path: 'competitions/new',
        loadComponent: () =>
          import('./pages/competitions/competition-create.page').then(
            (m) => m.CompetitionCreatePage,
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

  // Keep old URL working if bookmarked.
  { path: 'competitions/new', redirectTo: 'tabs/competitions/new', pathMatch: 'full' },
  {
    path: 'competitions/:id',
    canActivate: [authGuard],
    canMatch: [competitionIdCanMatch],
    loadComponent: () =>
      import('./pages/competitions/competition-detail.page').then(
        (m) => m.CompetitionDetailPage,
      ),
  },
  {
    path: 'competitions/:competitionId/fixtures/:fixtureId',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/fixtures/fixture-detail.page').then((m) => m.FixtureDetailPage),
  },
  {
    path: 'competitions/:id/setup',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/competitions/competition-setup.page').then((m) => m.CompetitionSetupPage),
  },

  { path: '**', redirectTo: 'tabs/competitions' },
];
