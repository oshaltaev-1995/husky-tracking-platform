import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { BrandMarkComponent } from '../../../shared/brand-mark/brand-mark.component';

@Component({
  selector: 'ht-home-page',
  imports: [BrandMarkComponent, RouterLink],
  templateUrl: './home-page.component.html',
  styleUrl: './home-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomePageComponent {
  protected readonly features = [
    { mark: '01', title: 'Daily Planning', copy: 'Plan training, open-space walks, individual exercise and intentional rest.', route: '/demo/daily' },
    { mark: '02', title: 'Team Builder', copy: 'Arrange explainable, role-aware and workload-aware lineups with manual control.', route: '/features' },
    { mark: '03', title: 'Daily Entry', copy: 'Confirm what actually happened without confusing plans with workload truth.', route: '/demo/daily-entry' },
    { mark: '04', title: 'Analytics', copy: 'Understand population composition, work patterns and workload-attention signals.', route: '/demo/analytics' },
    { mark: '05', title: 'Kennel Map', copy: 'Explore dated housing as a physical ground plan with operational visual layers.', route: '/demo/kennel' },
    { mark: '06', title: 'Dog Profiles', copy: 'Connect identity, pedigree, work, housing, status and historical records in one place.', route: '/demo/dogs' },
  ];
}
