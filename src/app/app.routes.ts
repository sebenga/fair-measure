import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadChildren: () => import('./tabs/tabs.routes').then((m) => m.routes),
  },
  {
    path: 'auth/login',
    loadComponent: () => import('./auth/login/login.page').then(m => m.LoginPage)
  },
  {
    path: 'auth/register',
    loadComponent: () => import('./auth/register/register.page').then(m => m.RegisterPage)
  },
  {
    path: 'create-competition',
    loadComponent: () => import('./create-competition/create-competition.page').then(m => m.CreateCompetitionPage)
  },
  {
    path: 'media-upload',
    loadComponent: () => import('./media-upload/media-upload.page').then(m => m.MediaUploadPage)
  },
];
