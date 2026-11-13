import type { CompetitionDetail, Stage } from './models';

/** A league's seasons in order, oldest first. Only worth a picker once there are two. */
export function seasonsOf(competition: CompetitionDetail): Stage[] {
  return competition.stages
    .filter((stage) => stage.kind === 'league')
    .sort((a, b) => a.display_order - b.display_order);
}

/** The season being played now: the newest one. */
export function currentSeason(competition: CompetitionDetail): Stage | null {
  const seasons = seasonsOf(competition);
  return seasons.length > 1 ? seasons[seasons.length - 1] : null;
}
