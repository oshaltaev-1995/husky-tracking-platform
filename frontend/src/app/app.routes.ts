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
    path: 'kennel',
    loadComponent: () =>
      import('./features/kennel-map/kennel-map-page.component').then(
        (component) => component.KennelMapPageComponent,
      ),
    title: 'Kennel Map · Husky Tracking',
    data: { layout: 'wide' },
  },
  {
    path: 'daily',
    loadComponent: () =>
      import('./features/daily-plan/daily-plan-page.component').then(
        (component) => component.DailyPlanPageComponent,
      ),
    title: 'Daily Plan · Husky Tracking',
    data: { layout: 'wide' },
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
