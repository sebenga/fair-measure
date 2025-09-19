import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadChildren: () => import('./tabs/tabs.routes').then((m) => m.routes),
  },
  {
    path: 'create-competition',
    loadComponent: () => import('./create-competition/create-competition.page').then(m => m.CreateCompetitionPage)
  },
];
