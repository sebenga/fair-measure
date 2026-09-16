import { CanMatchFn } from '@angular/router';

const COMPETITION_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Keep reserved paths like "new" from being treated as a competition id. */
export const competitionIdCanMatch: CanMatchFn = (_route, segments) => {
  const id = segments.at(-1)?.path;
  return !!id && COMPETITION_ID.test(id);
};
