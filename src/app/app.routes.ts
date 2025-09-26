import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full'
  },
  {
    path: 'login',
    loadComponent: () => import('./login/login.page').then(m => m.LoginPage)
  },
  {
    path: 'register',
    loadComponent: () => import('./register/register.page').then(m => m.RegisterPage)
  },
  {
    path: 'tabs',
    loadChildren: () => import('./tabs/tabs.routes').then((m) => m.routes),
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
