import { ApiService } from './api.service';
import { firstValueFrom } from 'rxjs';

export async function createSampleCompetitions(apiService: ApiService) {
  for (let i = 1; i <= 50; i++) {
    const competition = {
      name: `Competition ${i}`,
      description: `Sample description for competition ${i}`,
      image: `https://picsum.photos/80/80?random=${i}`
    };
    await firstValueFrom(apiService.createCompetition(competition));
  }
  console.log('50 sample competitions created!');
}

// Usage: Call createSampleCompetitions(apiService) from a component or service where ApiService is injected.
