import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dogs' },
  {
    path: 'dogs',
    loadComponent: () =>
      import('./features/dogs/dogs-registry.component').then(
        (component) => component.DogsRegistryComponent,
      ),
    title: 'Dogs · Husky Tracking',
  },
  {
    path: 'dogs/:dogId',
    loadComponent: () =>
      import('./features/dogs/profile/dog-profile.component').then(
        (component) => component.DogProfileComponent,
      ),
    title: 'Dog Profile · Husky Tracking',
  },
  {
    path: 'archive',
    loadComponent: () =>
      import('./features/archive/archive-registry.component').then(
        (component) => component.ArchiveRegistryComponent,
      ),
    title: 'Archive · Husky Tracking',
  },
  { path: '**', redirectTo: 'dogs' },
];
