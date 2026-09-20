import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'ht-brand-mark',
  template: '<img src="/brand-mark.png" alt="" width="96" height="96" />',
  styleUrl: './brand-mark.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BrandMarkComponent {}
