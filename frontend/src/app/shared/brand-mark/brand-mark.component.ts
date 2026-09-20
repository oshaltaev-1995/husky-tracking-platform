import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'ht-brand-mark',
  template: '<img src="/favicon.png" alt="" width="1254" height="1254" />',
  styleUrl: './brand-mark.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BrandMarkComponent {}
