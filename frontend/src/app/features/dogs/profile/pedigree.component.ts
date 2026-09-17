import { DatePipe, NgTemplateOutlet, TitleCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { DogPedigree } from '../../../core/api/dogs.models';

@Component({
  selector: 'ht-pedigree',
  imports: [DatePipe, NgTemplateOutlet, RouterLink, TitleCasePipe],
  template: `
    <section class="pedigree-intro"><div><p class="eyebrow">Family network</p><h2>Parents and grandparents</h2></div><p>Known kennel relatives remain linked regardless of lifecycle state.</p></section>
    <div class="parent-grid">
      <section class="family-branch"><h3>Mother</h3><ng-container [ngTemplateOutlet]="relation" [ngTemplateOutletContext]="{ dog: pedigree().mother, unknown: 'Unknown or external mother' }" /><h4>Maternal grandparents</h4><div class="grandparents"><ng-container [ngTemplateOutlet]="relation" [ngTemplateOutletContext]="{ dog: pedigree().maternal_grandparents.mother, unknown: 'Unknown grandmother' }" /><ng-container [ngTemplateOutlet]="relation" [ngTemplateOutletContext]="{ dog: pedigree().maternal_grandparents.father, unknown: 'Unknown grandfather' }" /></div></section>
      <section class="family-branch"><h3>Father</h3><ng-container [ngTemplateOutlet]="relation" [ngTemplateOutletContext]="{ dog: pedigree().father, unknown: 'Unknown or external father' }" /><h4>Paternal grandparents</h4><div class="grandparents"><ng-container [ngTemplateOutlet]="relation" [ngTemplateOutletContext]="{ dog: pedigree().paternal_grandparents.mother, unknown: 'Unknown grandmother' }" /><ng-container [ngTemplateOutlet]="relation" [ngTemplateOutletContext]="{ dog: pedigree().paternal_grandparents.father, unknown: 'Unknown grandfather' }" /></div></section>
    </div>
    <section class="family-section"><div class="section-heading"><div><p class="eyebrow">Litter</p><h2>{{ pedigree().litter ? pedigree().litter?.code + '-litter' : 'No recorded litter' }}</h2></div>@if (pedigree().litter) { <span>Born {{ pedigree().litter?.birth_date | date: 'longDate' }}</span> }</div>
      @if (pedigree().litter) { <div class="relation-grid">@for (sibling of pedigree().litter?.siblings; track sibling.id) { <ng-container [ngTemplateOutlet]="relation" [ngTemplateOutletContext]="{ dog: sibling }" /> } @empty { <p class="empty-copy">No other litter members are recorded.</p> }</div> } @else { <p class="empty-copy">This foundation dog has no litter record in the kennel database.</p> }
    </section>
    <section class="family-section"><div class="section-heading"><div><p class="eyebrow">Descendants</p><h2>Offspring</h2></div></div>
      @for (litter of pedigree().offspring; track litter.code) { <div class="offspring-group"><h3>{{ litter.code }}-litter <small>{{ litter.birth_date | date: 'mediumDate' }}</small></h3><div class="relation-grid">@for (child of litter.children; track child.id) { <ng-container [ngTemplateOutlet]="relation" [ngTemplateOutletContext]="{ dog: child }" /> }</div></div> } @empty { <p class="empty-copy">No offspring are represented in this dataset.</p> }
    </section>
    <ng-template #relation let-dog="dog" let-unknown="unknown">
      @if (dog) { <a class="relation-card" [routerLink]="['/dogs', dog.id]"><span class="relation-initial" aria-hidden="true">{{ dog.name.slice(0, 1) }}</span><span><strong>{{ dog.name }}</strong><small>{{ dog.dog_class | titlecase }} · born {{ dog.birth_date | date: 'yyyy' }}</small></span>@if (dog.lifecycle === 'archived') { <em>Archived</em> }<span class="arrow" aria-hidden="true">→</span></a> } @else { <div class="relation-card unknown"><span class="relation-initial" aria-hidden="true">?</span><span><strong>{{ unknown }}</strong><small>Not represented in this kennel dataset</small></span></div> }
    </ng-template>
  `,
  styleUrl: './pedigree.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PedigreeComponent {
  readonly pedigree = input.required<DogPedigree>();
}
