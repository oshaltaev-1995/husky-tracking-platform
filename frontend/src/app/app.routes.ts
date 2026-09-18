import { Routes } from '@angular/router';
import { demoSessionGuard } from './core/guards/demo-session.guard';

const demoRoutes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    loadComponent: () =>
      import('./features/dashboard/dashboard-page.component').then(
        (component) => component.DashboardPageComponent,
      ),
    title: 'Dashboard · Husky Tracking Demo',
    data: { layout: 'wide' },
  },
  {
    path: 'dogs',
    loadComponent: () =>
      import('./features/dogs/dogs-registry.component').then(
        (component) => component.DogsRegistryComponent,
      ),
    title: 'Dogs · Husky Tracking Demo',
  },
  {
    path: 'dogs/:dogId',
    loadComponent: () =>
      import('./features/dogs/profile/dog-profile.component').then(
        (component) => component.DogProfileComponent,
      ),
    title: 'Dog Profile · Husky Tracking Demo',
  },
  {
    path: 'kennel',
    loadComponent: () =>
      import('./features/kennel-map/kennel-map-page.component').then(
        (component) => component.KennelMapPageComponent,
      ),
    title: 'Kennel Map · Husky Tracking Demo',
    data: { layout: 'wide' },
  },
  {
    path: 'daily',
    loadComponent: () =>
      import('./features/daily-plan/daily-plan-page.component').then(
        (component) => component.DailyPlanPageComponent,
      ),
    title: 'Daily Plan · Husky Tracking Demo',
    data: { layout: 'wide' },
  },
  {
    path: 'daily/:date/activities/:activityId/teams',
    loadComponent: () =>
      import('./features/team-builder/team-builder-page.component').then(
        (component) => component.TeamBuilderPageComponent,
      ),
    title: 'Team Builder · Husky Tracking Demo',
    data: { layout: 'wide' },
  },
  {
    path: 'daily-entry',
    loadComponent: () =>
      import('./features/daily-entry/daily-entry-page.component').then(
        (component) => component.DailyEntryPageComponent,
      ),
    title: 'Daily Entry · Husky Tracking Demo',
    data: { layout: 'wide' },
  },
  {
    path: 'analytics',
    loadComponent: () =>
      import('./features/analytics/analytics-page.component').then(
        (component) => component.AnalyticsPageComponent,
      ),
    title: 'Analytics · Husky Tracking Demo',
    data: { layout: 'wide' },
  },
  {
    path: 'archive',
    loadComponent: () =>
      import('./features/archive/archive-registry.component').then(
        (component) => component.ArchiveRegistryComponent,
      ),
    title: 'Archive · Husky Tracking Demo',
  },
];

export const routes: Routes = [
  {
    path: 'demo',
    loadComponent: () =>
      import('./layout/demo-shell/demo-shell.component').then(
        (component) => component.DemoShellComponent,
      ),
    canActivate: [demoSessionGuard],
    canActivateChild: [demoSessionGuard],
    children: demoRoutes,
  },

  // Legacy links remain redirects only; `/demo/...` is the single canonical app tree.
  { path: 'dashboard', pathMatch: 'full', redirectTo: 'demo/dashboard' },
  { path: 'dogs', pathMatch: 'full', redirectTo: 'demo/dogs' },
  { path: 'dogs/:dogId', pathMatch: 'full', redirectTo: 'demo/dogs/:dogId' },
  { path: 'kennel', pathMatch: 'full', redirectTo: 'demo/kennel' },
  { path: 'daily', pathMatch: 'full', redirectTo: 'demo/daily' },
  {
    path: 'daily/:date/activities/:activityId/teams',
    pathMatch: 'full',
    redirectTo: 'demo/daily/:date/activities/:activityId/teams',
  },
  { path: 'daily-entry', pathMatch: 'full', redirectTo: 'demo/daily-entry' },
  { path: 'analytics', pathMatch: 'full', redirectTo: 'demo/analytics' },
  { path: 'archive', pathMatch: 'full', redirectTo: 'demo/archive' },

  {
    path: '',
    loadComponent: () =>
      import('./layout/public-shell/public-shell.component').then(
        (component) => component.PublicShellComponent,
      ),
    children: [
      {
        path: '',
        pathMatch: 'full',
        loadComponent: () =>
          import('./features/public/home/home-page.component').then(
            (component) => component.HomePageComponent,
          ),
        title: 'Husky Tracking — Sled-dog kennel operations demo',
        data: {
          description:
            'Explore a modern sled-dog kennel operations platform through a safe, fictional interactive demo.',
        },
      },
      {
        path: 'features',
        loadComponent: () =>
          import('./features/public/features/features-page.component').then(
            (component) => component.FeaturesPageComponent,
          ),
        title: 'Features — Husky Tracking',
        data: {
          description:
            'Explore dog profiles, historical housing, daily planning, team building, actual work and workload analytics.',
        },
      },
      {
        path: 'about',
        loadComponent: () =>
          import('./features/public/about/about-page.component').then(
            (component) => component.AboutPageComponent,
          ),
        title: 'About — Husky Tracking',
        data: {
          description:
            'Learn how Husky Tracking became a full-stack portfolio demonstration built with deterministic synthetic data.',
        },
      },
      {
        path: 'contact',
        loadComponent: () =>
          import('./features/public/contact/contact-page.component').then(
            (component) => component.ContactPageComponent,
          ),
        title: 'Contact — Husky Tracking',
        data: {
          description:
            'Contact the Husky Tracking project about its product design and software implementation.',
        },
      },
      {
        path: 'privacy',
        loadComponent: () =>
          import('./features/public/privacy/privacy-page.component').then(
            (component) => component.PrivacyPageComponent,
          ),
        title: 'Privacy — Husky Tracking',
        data: {
          description:
            'How Husky Tracking handles anonymous demo sessions, contact messages and public-site data.',
        },
      },
      {
        path: '**',
        loadComponent: () =>
          import('./features/public/not-found/not-found-page.component').then(
            (component) => component.NotFoundPageComponent,
          ),
        title: 'Page not found — Husky Tracking',
        data: { description: 'The requested Husky Tracking page could not be found.' },
      },
    ],
  },
];
