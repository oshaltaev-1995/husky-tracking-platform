import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import {
  PlannedTeam,
  TeamBuilderCandidate,
  TeamBuilderContext,
  TeamSlot,
  UnassignedDog,
} from '../../core/api/team-builder.models';
import { TeamBuilderService } from '../../core/api/team-builder.service';
import { WorkingRole } from '../../core/api/dogs.models';
import { CountLabelPipe } from '../../shared/count-label/count-label.pipe';
import { workingRoleLabel, workingRoleList } from '../../shared/working-role-label';

interface DraftSlot extends Omit<TeamSlot, 'dog_id' | 'dog_name'> {
  dog_id: string | null;
  dog_name: string | null;
}

interface DraftTeam extends Omit<PlannedTeam, 'slots'> {
  slots: DraftSlot[];
}

interface SlotAddress {
  teamIndex: number;
  slotIndex: number;
}

@Component({
  selector: 'ht-team-builder-page',
  imports: [CountLabelPipe, FormsModule, RouterLink],
  templateUrl: './team-builder-page.component.html',
  styleUrl: './team-builder-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TeamBuilderPageComponent {
  private readonly api = inject(TeamBuilderService);
  private readonly route = inject(ActivatedRoute);

  protected readonly context = signal<TeamBuilderContext | null>(null);
  protected readonly loading = signal(true);
  protected readonly busy = signal(false);
  protected readonly error = signal('');
  protected readonly success = signal('');
  protected readonly teams = signal<DraftTeam[]>([]);
  protected readonly unassigned = signal<UnassignedDog[]>([]);
  protected readonly editing = signal(false);
  protected readonly generated = signal(false);
  protected readonly confirmingRebuild = signal(false);
  protected readonly selectedSlot = signal<SlotAddress | null>(null);
  protected readonly editError = signal('');
  protected readonly eligibleCandidates = computed(
    () => this.context()?.candidates.filter((dog) => dog.eligible) ?? [],
  );
  protected readonly ineligibleCandidates = computed(
    () => this.context()?.candidates.filter((dog) => !dog.eligible) ?? [],
  );

  protected date = '';
  protected activityId = '';
  protected teamCount = 1;
  protected teamSize = 8;

  constructor() {
    this.route.paramMap.subscribe((params) => {
      this.date = params.get('date') ?? '';
      this.activityId = params.get('activityId') ?? '';
      this.load();
    });
  }

  protected generate(): void {
    const context = this.context();
    if (!context || this.busy()) return;
    if (context.saved_teams.length && !this.confirmingRebuild()) {
      this.confirmingRebuild.set(true);
      return;
    }
    this.confirmingRebuild.set(false);
    this.busy.set(true);
    this.error.set('');
    this.success.set('');
    this.api.generate(this.date, this.activityId, this.teamCount, this.teamSize).subscribe({
      next: (result) => {
        this.teams.set(this.toDraft(result.teams));
        this.unassigned.set(result.unassigned);
        this.editing.set(true);
        this.generated.set(true);
        this.busy.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.error.set(this.errorMessage(error));
        this.busy.set(false);
      },
    });
  }

  protected editSaved(): void {
    const context = this.context();
    if (!context) return;
    this.teams.set(this.toDraft(context.saved_teams));
    this.unassigned.set(this.unassignedFor(context.saved_teams));
    this.editing.set(true);
    this.generated.set(false);
    this.editError.set('');
  }

  protected cancelEditing(): void {
    const context = this.context();
    if (!context) return;
    this.teams.set(this.toDraft(context.saved_teams));
    this.unassigned.set(this.unassignedFor(context.saved_teams));
    this.editing.set(false);
    this.generated.set(false);
    this.selectedSlot.set(null);
    this.editError.set('');
  }

  protected selectSlot(teamIndex: number, slotIndex: number): void {
    if (!this.editing()) return;
    const current = this.selectedSlot();
    if (!current) {
      this.selectedSlot.set({ teamIndex, slotIndex });
      return;
    }
    if (current.teamIndex === teamIndex && current.slotIndex === slotIndex) {
      this.selectedSlot.set(null);
      return;
    }
    const before = structuredClone(this.teams()) as DraftTeam[];
    const teams = structuredClone(before) as DraftTeam[];
    const source = teams[current.teamIndex].slots[current.slotIndex];
    const target = teams[teamIndex].slots[slotIndex];
    [source.dog_id, target.dog_id] = [target.dog_id, source.dog_id];
    [source.dog_name, target.dog_name] = [target.dog_name, source.dog_name];
    source.explanations = source.dog_id
      ? [`${this.roleLabel(source.harness_role)} capable`, 'Manual swap']
      : [];
    target.explanations = target.dog_id
      ? [`${this.roleLabel(target.harness_role)} capable`, 'Manual swap']
      : [];
    const issue = this.validateDraft(teams);
    if (issue) {
      this.editError.set(issue);
    } else {
      this.teams.set(teams);
      this.editError.set('');
    }
    this.selectedSlot.set(null);
  }

  protected clearSlot(teamIndex: number, slotIndex: number): void {
    const teams = structuredClone(this.teams()) as DraftTeam[];
    const slot = teams[teamIndex].slots[slotIndex];
    if (slot.dog_id && slot.dog_name) {
      this.unassigned.update((dogs) => [
        ...dogs,
        { dog_id: slot.dog_id!, dog_name: slot.dog_name!, reason: 'Cleared during editing' },
      ]);
    }
    slot.dog_id = null;
    slot.dog_name = null;
    slot.explanations = [];
    this.teams.set(teams);
    this.selectedSlot.set(null);
    this.editError.set('Fill every harness slot before saving.');
  }

  protected placeUnassigned(dog: UnassignedDog): void {
    const address = this.selectedSlot();
    if (!address) {
      this.editError.set('Select a harness slot first.');
      return;
    }
    const before = structuredClone(this.teams()) as DraftTeam[];
    const teams = structuredClone(before) as DraftTeam[];
    const slot = teams[address.teamIndex].slots[address.slotIndex];
    const previous = slot.dog_id && slot.dog_name
      ? { dog_id: slot.dog_id, dog_name: slot.dog_name, reason: 'Replaced during editing' }
      : null;
    slot.dog_id = dog.dog_id;
    slot.dog_name = dog.dog_name;
    slot.explanations = [`${this.roleLabel(slot.harness_role)} capable`, 'Manual choice'];
    const issue = this.validateDraft(teams);
    if (issue) {
      this.editError.set(issue);
      return;
    }
    this.teams.set(teams);
    this.unassigned.update((dogs) => [
      ...dogs.filter((item) => item.dog_id !== dog.dog_id),
      ...(previous ? [previous] : []),
    ]);
    this.selectedSlot.set(null);
    this.editError.set('');
  }

  protected save(): void {
    const context = this.context();
    if (!context || this.busy()) return;
    const issue = this.validateDraft(this.teams());
    if (issue) {
      this.editError.set(issue);
      return;
    }
    this.busy.set(true);
    this.editError.set('');
    this.api
      .save(this.date, this.activityId, {
        expected_revision: context.activity.plan_revision,
        replace_existing: context.saved_teams.length > 0,
        teams: this.teams().map((team) => ({
          sequence: team.sequence,
          display_label: team.display_label,
          team_size: team.team_size,
          slots: team.slots.map((slot) => ({
            dog_id: slot.dog_id!,
            pair_index: slot.pair_index,
            side: slot.side,
            harness_role: slot.harness_role,
            position_order: slot.position_order,
          })),
        })),
      })
      .subscribe({
        next: (updated) => {
          this.acceptContext(updated);
          this.editing.set(false);
          this.generated.set(false);
          this.busy.set(false);
          this.success.set('Team lineup saved to the Daily Plan.');
        },
        error: (error: HttpErrorResponse) => {
          this.editError.set(this.errorMessage(error));
          this.busy.set(false);
        },
      });
  }

  protected isSelected(teamIndex: number, slotIndex: number): boolean {
    const selected = this.selectedSlot();
    return selected?.teamIndex === teamIndex && selected.slotIndex === slotIndex;
  }

  protected candidate(dogId: string | null): TeamBuilderCandidate | undefined {
    return this.context()?.candidates.find((dog) => dog.id === dogId);
  }

  protected roleLabel(role: WorkingRole): string {
    return workingRoleLabel(role);
  }

  protected sideLabel(side: string): string {
    return side.replace(/^./, (character) => character.toUpperCase());
  }

  protected roleList(roles: WorkingRole[]): string {
    return workingRoleList(roles);
  }

  protected softWarnings(): string[] {
    const context = this.context();
    if (!context || !this.teams().length) return [];
    const positions = new Map<string, string>();
    for (const team of this.teams()) {
      for (const slot of team.slots) {
        if (slot.dog_id) positions.set(slot.dog_id, `${team.sequence}:${slot.pair_index}`);
      }
    }
    return context.relationships
      .filter(
        (relation) =>
          relation.kind === 'preferred_pair' &&
          positions.has(relation.dog_a_id) &&
          positions.has(relation.dog_b_id) &&
          positions.get(relation.dog_a_id) !== positions.get(relation.dog_b_id),
      )
      .map((relation) => {
        const first = this.candidate(relation.dog_a_id)?.name;
        const second = this.candidate(relation.dog_b_id)?.name;
        return `Preferred pair separated: ${first} and ${second}`;
      });
  }

  protected requiredRoleCount(): number {
    return this.teamCount * 2;
  }

  protected pairIndexes(team: DraftTeam): number[] {
    return Array.from({ length: team.team_size / 2 }, (_, index) => index);
  }

  protected pairSlots(team: DraftTeam, pairIndex: number): DraftSlot[] {
    return team.slots
      .filter((slot) => slot.pair_index === pairIndex)
      .sort((first, second) => first.position_order - second.position_order);
  }

  private load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.getContext(this.date, this.activityId).subscribe({
      next: (context) => {
        this.acceptContext(context);
        this.teamCount = context.saved_teams.length || context.recommended_team_count;
        this.teamSize = context.saved_teams[0]?.team_size ?? context.recommended_team_size;
        this.loading.set(false);
      },
      error: (error: HttpErrorResponse) => {
        this.error.set(this.errorMessage(error));
        this.loading.set(false);
      },
    });
  }

  private acceptContext(context: TeamBuilderContext): void {
    this.context.set(context);
    this.teams.set(this.toDraft(context.saved_teams));
    this.unassigned.set(this.unassignedFor(context.saved_teams));
    this.selectedSlot.set(null);
  }

  private toDraft(teams: PlannedTeam[]): DraftTeam[] {
    return structuredClone(teams) as DraftTeam[];
  }

  private unassignedFor(teams: PlannedTeam[]): UnassignedDog[] {
    const assigned = new Set(teams.flatMap((team) => team.slots.map((slot) => slot.dog_id)));
    return this.eligibleCandidates()
      .filter((dog) => !assigned.has(dog.id))
      .map((dog) => ({
        dog_id: dog.id,
        dog_name: dog.name,
        reason: 'Not assigned to a saved team',
      }));
  }

  private validateDraft(teams: DraftTeam[]): string {
    const context = this.context();
    if (!context) return 'Team Builder context is unavailable.';
    const used = new Set<string>();
    for (const team of teams) {
      for (const slot of team.slots) {
        if (!slot.dog_id) return 'Fill every harness slot before saving.';
        const dog = this.candidate(slot.dog_id);
        if (!dog?.eligible) return `${slot.dog_name} is no longer eligible.`;
        if (!dog.capabilities.includes(slot.harness_role)) {
          return `${dog.name} is not ${this.roleLabel(slot.harness_role)} capable.`;
        }
        if (used.has(slot.dog_id)) return `${dog.name} appears more than once.`;
        used.add(slot.dog_id);
      }
      for (let pairIndex = 0; pairIndex < team.team_size / 2; pairIndex += 1) {
        const pair = team.slots.filter((slot) => slot.pair_index === pairIndex);
        const conflict = context.relationships.find(
          (relation) =>
            relation.kind === 'hard_conflict' &&
            pair.some((slot) => slot.dog_id === relation.dog_a_id) &&
            pair.some((slot) => slot.dog_id === relation.dog_b_id),
        );
        if (conflict) {
          return `Cannot pair ${this.candidate(conflict.dog_a_id)?.name} with ${this.candidate(conflict.dog_b_id)?.name}.`;
        }
      }
    }
    return '';
  }

  private errorMessage(error: HttpErrorResponse): string {
    const detail = error.error?.detail;
    if (typeof detail === 'object' && typeof detail?.message === 'string') return detail.message;
    return 'Team Builder could not complete that request. Try again.';
  }
}
