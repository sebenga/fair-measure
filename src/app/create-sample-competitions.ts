import { ApiService, CompetitionPayload } from './api.service';
import { firstValueFrom } from 'rxjs';

function buildSampleCompetition(index: number): CompetitionPayload {
  const ownerId = crypto.randomUUID();
  return {
    id: crypto.randomUUID(),
    name: `Competition ${index}`,
    author: 'Sample User',
    owner_id: ownerId,
    date_created: new Date().toISOString(),
    logo_location: `https://picsum.photos/80/80?random=${index}`,
    is_private: false,
    type: 'league',
    rules: [
      {
        name: 'General rules',
        description: `Sample description for competition ${index}`,
      },
    ],
    scoring_categories: [{ name: 'Points', description: 'Standard scoring', points: 1 }],
    point_accumulation: { win: 3, lose: 0, draw: 1 },
    participants: ['Sample User'],
    fixtures: [],
    league_table: [],
    posts: [],
    photos: [],
    videos: [],
  };
}

export async function createSampleCompetitions(apiService: ApiService): Promise<void> {
  for (let i = 1; i <= 50; i++) {
    await firstValueFrom(apiService.createCompetition(buildSampleCompetition(i)));
  }
  console.log('50 sample competitions created!');
}
