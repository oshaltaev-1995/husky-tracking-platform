import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export type NavIconName = 'dashboard' | 'dogs' | 'kennel' | 'daily' | 'entry' | 'analytics' | 'archive' | 'exit';

@Component({
  selector: 'ht-nav-icon',
  template: `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
      @switch (name()) {
        @case ('dashboard') { <path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V10Z"/><path d="M9 21v-7h6v7"/> }
        @case ('dogs') { <circle cx="6" cy="9" r="1"/><circle cx="10" cy="5" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="19" cy="9" r="1"/><path d="M8.5 13.5c1.1-1.4 2-2 3.5-2s2.4.6 3.5 2l2.1 2.6c1.4 1.8.3 4.4-2 4.4-1.2 0-2.2-.7-3.6-.7s-2.4.7-3.6.7c-2.3 0-3.4-2.6-2-4.4l2.1-2.6Z"/> }
        @case ('kennel') { <path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2V5Z"/><path d="M9 3v16M15 5v16"/><path d="m11 10 1-1 1 1-1 1-1-1Z"/> }
        @case ('daily') { <rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M8 14h3M8 17h3"/> }
        @case ('entry') { <rect x="5" y="4" width="14" height="18" rx="2"/><path d="M9 4.5V3h6v1.5M9 11h6M9 15l2 2 4-4"/> }
        @case ('analytics') { <path d="M4 20h16M6 17v-5h3v5M11 17V7h3v10M16 17v-8h3v8"/> }
        @case ('archive') { <rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v11h14V9M10 13h4"/> }
        @case ('exit') { <path d="M11 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h6M16 7l5 5-5 5M21 12H9"/> }
      }
    </svg>
  `,
  styles: [':host { display: block; width: 1rem; height: 1rem; } svg { display: block; width: 100%; height: 100%; }'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NavIconComponent {
  readonly name = input.required<NavIconName>();
}
