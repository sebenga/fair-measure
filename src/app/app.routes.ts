import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './guards/auth.guard';
import { TabsPage } from './tabs/tabs.page';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'home',
    pathMatch: 'full',
  },
  {
    path: 'auth/login',
    loadComponent: () => import('./auth/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'auth/register',
    loadComponent: () => import('./auth/register/register.page').then((m) => m.RegisterPage),
    canActivate: [guestGuard],
  },
  {
    path: 'home',
    component: TabsPage,
    children: [
      {
        path: '',
        loadComponent: () => import('./tab1/tab1.page').then((m) => m.Tab1Page),
      },
      {
        path: 'tab2',
        loadComponent: () => import('./tab2/tab2.page').then((m) => m.Tab2Page),
        canActivate: [authGuard],
      },
      {
        path: 'tab3',
        loadComponent: () => import('./tab3/tab3.page').then((m) => m.Tab3Page),
        canActivate: [authGuard],
      },
    ],
  },
  {
    path: 'create-competition',
    loadComponent: () =>
      import('./create-competition/create-competition.page').then((m) => m.CreateCompetitionPage),
    canActivate: [authGuard],
  },
  {
    path: 'media-upload',
    loadComponent: () =>
      import('./media-upload/media-upload.page').then((m) => m.MediaUploadPage),
    canActivate: [authGuard],
  },
  {
    path: 'login',
    redirectTo: 'home',
    pathMatch: 'full',
  },
  {
    path: 'register',
    redirectTo: 'home',
    pathMatch: 'full',
  },
];
