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
    { mark: '01', title: 'Kennel Map', copy: 'Explore dated housing as a physical ground plan with operational visual layers.', route: '/demo/kennel' },
    { mark: '02', title: 'Dog Profiles', copy: 'Connect identity, pedigree, work, housing, status and historical records in one place.', route: '/demo/dogs' },
    { mark: '03', title: 'Daily Planning', copy: 'Plan training, open-space walks, individual exercise and intentional rest.', route: '/demo/daily' },
    { mark: '04', title: 'Team Builder', copy: 'Arrange explainable, role-aware and workload-aware lineups with manual control.', route: '/features' },
    { mark: '05', title: 'Daily Entry', copy: 'Confirm what actually happened without confusing plans with workload truth.', route: '/demo/daily-entry' },
    { mark: '06', title: 'Analytics', copy: 'Understand population composition, work patterns and workload-attention signals.', route: '/demo/analytics' },
  ];
}
