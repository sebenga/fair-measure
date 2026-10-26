import type { Fixture, Stage } from '../../../core/models';

export function cupStageOf(fixture: Fixture, stages: Stage[] = []): Stage | undefined {
  return stages.find((stage) => stage.kind === 'knockout' && stage.id === fixture.stage);
}

export function cupNameOf(fixture: Fixture, stages: Stage[] = []): string {
  return cupStageOf(fixture, stages)?.name || 'Cup';
}

export function isCupFixture(fixture: Fixture, stages: Stage[] = []): boolean {
  if (cupStageOf(fixture, stages)) return true;
  const knockoutIds = stages.filter((stage) => stage.kind === 'knockout').map((stage) => stage.id);
  if (knockoutIds.length && fixture.stage) {
    return knockoutIds.includes(fixture.stage);
  }
  const label = (fixture.label || '').trim().toLowerCase();
  return label.startsWith('cup') || label === 'bye';
}

export function cupRoundName(ties: number, round: number, totalRounds: number): string {
  const fromEnd = totalRounds - round;
  if (fromEnd === 0 || ties === 1) return 'Final';
  if (fromEnd === 1 || ties === 2) return 'Semi-finals';
  if (fromEnd === 2 || ties === 4) return 'Quarter-finals';
  if (fromEnd === 3 || ties === 8) return 'Round of 16';
  if (ties === 16) return 'Round of 32';
  return `Round ${round}`;
}
