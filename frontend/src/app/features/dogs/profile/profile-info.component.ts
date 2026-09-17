import { DatePipe, TitleCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { DogProfile } from '../../../core/api/dogs.models';

@Component({
  selector: 'ht-profile-info',
  imports: [DatePipe, TitleCasePipe],
  template: `
    <section class="detail-section" aria-labelledby="identity-title">
      <div class="section-heading"><p class="eyebrow">Identity</p><h2 id="identity-title">Kennel record</h2></div>
      <dl class="facts-grid">
        <div><dt>Full name</dt><dd>{{ dog().name }}</dd></div>
        <div><dt>Date of birth</dt><dd>{{ dog().birth_date | date: 'longDate' }}</dd></div>
        <div><dt>Age at demo date</dt><dd>{{ dog().age_label }}</dd></div>
        <div><dt>Sex</dt><dd>{{ dog().sex | titlecase }}</dd></div>
        <div><dt>Neutered / spayed</dt><dd>{{ dog().is_neutered ? 'Yes' : 'No' }} @if (dog().neutered_on) { <small>since {{ dog().neutered_on | date: 'mediumDate' }}</small> }</dd></div>
        <div><dt>Litter</dt><dd>{{ dog().litter_code ? dog().litter_code + '-litter' : 'Foundation dog' }}</dd></div>
        <div><dt>Lifecycle</dt><dd>{{ dog().state.lifecycle | titlecase }}</dd></div>
        <div><dt>Class</dt><dd>{{ dog().state.dog_class | titlecase }} @if (dog().state.class_is_historical) { <small>last assigned</small> }</dd></div>
        <div><dt>Availability</dt><dd>{{ dog().state.availability ? (dog().state.availability | titlecase) : 'Not current' }}</dd></div>
        <div><dt>{{ dog().state.housing ? 'Current housing' : 'Last known housing' }}</dt><dd>{{ dog().state.housing?.code || dog().last_known_housing?.code || 'No assignment' }}</dd></div>
      </dl>
    </section>
    <section class="detail-section" aria-labelledby="capabilities-title">
      <div class="section-heading"><p class="eyebrow">Operational fit</p><h2 id="capabilities-title">Working capabilities</h2></div>
      <div class="role-grid">
        @for (role of ['lead', 'team', 'wheel']; track role) {
          <div [class.enabled]="dog().capabilities.includes($any(role))"><span aria-hidden="true">{{ dog().capabilities.includes($any(role)) ? '✓' : '—' }}</span><strong>{{ role | titlecase }}</strong><small>{{ dog().capabilities.includes($any(role)) ? 'Eligible' : 'Not assigned' }}</small></div>
        }
      </div>
    </section>
  `,
  styles: `
    :host { display: grid; gap: 1rem; }
    .detail-section { padding: clamp(1rem, 3vw, 1.7rem); border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--surface); }
    .section-heading { margin-bottom: 1.25rem; } .section-heading h2 { margin: .15rem 0 0; font-family: Georgia, serif; font-size: 1.65rem; font-weight: 500; }
    .facts-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0; margin: 0; }
    .facts-grid div { padding: .9rem 1rem .9rem 0; border-top: 1px solid var(--line); }
    dt { color: var(--ink-soft); font-size: .69rem; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
    dd { margin: .25rem 0 0; font-weight: 700; } dd small { display: block; margin-top: .2rem; color: var(--ink-soft); font-weight: 500; }
    .role-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: .7rem; }
    .role-grid div { display: grid; grid-template-columns: auto 1fr; gap: .1rem .55rem; padding: .9rem; border: 1px solid var(--line); border-radius: .65rem; color: var(--ink-soft); }
    .role-grid span { grid-row: span 2; } .role-grid small { font-size: .72rem; } .role-grid .enabled { border-color: #9abeb5; color: var(--accent-deep); background: var(--accent-pale); }
    @media (max-width: 700px) { .facts-grid { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 440px) { .facts-grid, .role-grid { grid-template-columns: 1fr; } }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfileInfoComponent {
  readonly dog = input.required<DogProfile>();
}
