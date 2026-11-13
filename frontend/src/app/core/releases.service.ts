import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, computed, effect, inject, signal, untracked } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Observable, firstValueFrom, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

export type FeatureKey = 'games' | 'scouting' | 'fantasy' | 'discover' | 'partnerships' | 'horses';

export interface ReleaseState {
  features: Partial<Record<FeatureKey, boolean>>;
  platform_admin: boolean;
  /** Only the platform owner account may delete every competition. */
  clear_leagues?: boolean;
}

export interface ClearedCounts {
  competitions: number;
  fixtures: number;
  participants: number;
  games_events: number;
}

export interface ReleaseFeature {
  key: FeatureKey;
  label: string;
  description: string;
  live: boolean;
}

export interface ReleaseSport {
  key: string;
  label: string;
  icon: string;
  kind: string;
  group: string;
  group_label: string;
  family_label: string;
  live: boolean;
  competitions: number;
}

export interface ReleaseCatalogue {
  features: ReleaseFeature[];
  sports: ReleaseSport[];
}

export interface PlatformCompetition {
  id: string;
  name: string;
  sport: string;
  preset: string;
  preset_label: string;
  sport_live: boolean;
  status: string;
  is_private: boolean;
  platform_hidden: boolean;
  owner: string;
  participants: number;
  created_at: string;
}

/** Until the server answers, features are assumed open except the horse register. */
const OPTIMISTIC: Record<FeatureKey, boolean> = {
  games: true,
  scouting: true,
  fantasy: true,
  discover: true,
  partnerships: true,
  horses: false,
};

@Injectable({ providedIn: 'root' })
export class ReleasesService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly base = environment.apiBaseUrl;

  private readonly state = signal<ReleaseState | null>(null);
  private pending: Promise<ReleaseState | null> | null = null;

  readonly platformAdmin = computed(() => this.state()?.platform_admin ?? false);
  readonly canClearLeagues = computed(() => this.state()?.clear_leagues ?? false);

  constructor() {
    effect(() => {
      this.auth.user();
      untracked(() => void this.refresh());
    });
  }

  /** Released to everyone. The platform admin sees exactly what the public sees. */
  isOpen(feature: FeatureKey): boolean {
    return this.state()?.features[feature] ?? OPTIMISTIC[feature];
  }

  refresh(): Promise<ReleaseState | null> {
    this.pending = firstValueFrom(this.http.get<ReleaseState>(`${this.base}/platform/releases`))
      .then((state) => {
        this.state.set(state);
        return state;
      })
      .catch(() => this.state());
    return this.pending;
  }

  ready(): Promise<ReleaseState | null> {
    return this.state() ? Promise.resolve(this.state()) : (this.pending ?? this.refresh());
  }

  catalogue(): Observable<ReleaseCatalogue> {
    return this.http.get<ReleaseCatalogue>(`${this.base}/platform/admin/releases`);
  }

  setLive(kind: 'sport' | 'feature', keys: string[], live: boolean): Observable<ReleaseCatalogue> {
    return this.http
      .post<ReleaseCatalogue>(`${this.base}/platform/admin/releases`, { kind, keys, live })
      .pipe(tap(() => void this.refresh()));
  }

  competitions(search = '', hiddenOnly = false): Observable<{ count: number; results: PlatformCompetition[] }> {
    let params = new HttpParams();
    if (search) params = params.set('search', search);
    if (hiddenOnly) params = params.set('hidden', '1');
    return this.http.get<{ count: number; results: PlatformCompetition[] }>(
      `${this.base}/platform/admin/competitions`,
      { params },
    );
  }

  clearAllCompetitions(confirm: string): Observable<{ cleared: ClearedCounts }> {
    return this.http.post<{ cleared: ClearedCounts }>(`${this.base}/platform/admin/competitions/clear`, {
      confirm,
    });
  }

  setCompetitionHidden(id: string, hidden: boolean): Observable<PlatformCompetition> {
    return this.http.patch<PlatformCompetition>(`${this.base}/platform/admin/competitions/${id}`, {
      platform_hidden: hidden,
    });
  }
}

export function featureGuard(feature: FeatureKey): CanActivateFn {
  return async () => {
    const releases = inject(ReleasesService);
    const router = inject(Router);
    await releases.ready();
    return releases.isOpen(feature) ? true : router.createUrlTree(['/tabs/competitions']);
  };
}

export const platformAdminGuard: CanActivateFn = async () => {
  const releases = inject(ReleasesService);
  const router = inject(Router);
  await releases.ready();
  return releases.platformAdmin() ? true : router.createUrlTree(['/tabs/competitions']);
};
