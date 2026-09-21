import { WorkingRole } from '../core/api/dogs.models';

const WORKING_ROLE_LABELS: Record<WorkingRole, string> = {
  lead: 'Lead',
  team: 'Team',
  wheel: 'Wheel',
};

export function workingRoleLabel(role: WorkingRole): string {
  return WORKING_ROLE_LABELS[role];
}

export function workingRoleList(roles: readonly WorkingRole[]): string {
  return roles.map(workingRoleLabel).join(' · ');
}
