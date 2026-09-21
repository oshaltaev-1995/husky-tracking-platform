import { workingRoleLabel, workingRoleList } from './working-role-label';

describe('working role labels', () => {
  it('keeps canonical values separate from consistent visible labels', () => {
    expect(workingRoleLabel('lead')).toBe('Lead');
    expect(workingRoleLabel('team')).toBe('Team');
    expect(workingRoleLabel('wheel')).toBe('Wheel');
    expect(workingRoleList(['lead', 'team', 'wheel'])).toBe('Lead · Team · Wheel');
  });
});
