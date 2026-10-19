import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/auth.guard';
import { competitionIdCanMatch } from './core/competition-id.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'tabs/competitions', pathMatch: 'full' },

  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./pages/login/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'register',
    canActivate: [guestGuard],
    loadComponent: () => import('./pages/register/register.page').then((m) => m.RegisterPage),
  },

  {
    path: 'tabs',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/tabs/tabs.page').then((m) => m.TabsPage),
    children: [
      { path: '', redirectTo: 'competitions', pathMatch: 'full' },
      {
        path: 'competitions/new',
        loadComponent: () =>
          import('./pages/competitions/competition-create.page').then(
            (m) => m.CompetitionCreatePage,
          ),
      },
      {
        path: 'competitions/:id/setup',
        loadComponent: () =>
          import('./pages/competitions/competition-setup.page').then(
            (m) => m.CompetitionSetupPage,
          ),
      },
      {
        path: 'competitions/:id/score',
        loadComponent: () =>
          import('./pages/competitions/competition-score.page').then(
            (m) => m.CompetitionScorePage,
          ),
      },
      {
        path: 'competitions/:id/teams/:participantId',
        loadComponent: () =>
          import('./pages/competitions/team-profile.page').then((m) => m.TeamProfilePage),
      },
      {
        path: 'competitions/:id/players/:userId',
        loadComponent: () =>
          import('./pages/competitions/player-profile.page').then((m) => m.PlayerProfilePage),
      },
      {
        path: 'competitions/:competitionId/fixtures/:fixtureId',
        loadComponent: () =>
          import('./pages/fixtures/fixture-detail.page').then((m) => m.FixtureDetailPage),
      },
      {
        path: 'competitions/:id',
        canMatch: [competitionIdCanMatch],
        loadComponent: () =>
          import('./pages/competitions/competition-detail.page').then(
            (m) => m.CompetitionDetailPage,
          ),
      },
      {
        path: 'competitions',
        loadComponent: () =>
          import('./pages/competitions/competition-list.page').then(
            (m) => m.CompetitionListPage,
          ),
      },
      {
        path: 'discover',
        loadComponent: () =>
          import('./pages/discover/discover.page').then((m) => m.DiscoverPage),
      },
      {
        path: 'profile',
        loadComponent: () => import('./pages/profile/profile.page').then((m) => m.ProfilePage),
      },
      {
        path: 'scouting',
        loadComponent: () =>
          import('./pages/scouting/scouting-hub.page').then((m) => m.ScoutingHubPage),
      },
      {
        path: 'scouting/profile',
        loadComponent: () =>
          import('./pages/scouting/talent-profile.page').then((m) => m.TalentProfilePage),
      },
      {
        path: 'scouting/guardian',
        loadComponent: () => import('./pages/scouting/guardian.page').then((m) => m.GuardianPage),
      },
      {
        path: 'scouting/players',
        loadComponent: () =>
          import('./pages/scouting/players.page').then((m) => m.ScoutingPlayersPage),
      },
      {
        path: 'scouting/players/:id',
        loadComponent: () =>
          import('./pages/scouting/player-view.page').then((m) => m.ScoutingPlayerViewPage),
      },
      {
        path: 'scouting/players/:id/report',
        loadComponent: () =>
          import('./pages/scouting/scouting-report.page').then((m) => m.ScoutingReportPage),
      },
      {
        path: 'competitions/:competitionId/events/:fixtureId',
        loadComponent: () =>
          import('./pages/results/event-results.page').then((m) => m.EventResultsPage),
      },
      {
        path: 'games',
        loadComponent: () => import('./pages/games/games-list.page').then((m) => m.GamesListPage),
      },
      {
        path: 'games/:id',
        loadComponent: () => import('./pages/games/games-home.page').then((m) => m.GamesHomePage),
      },
      {
        path: 'games/:id/sports',
        loadComponent: () => import('./pages/games/games-sports.page').then((m) => m.GamesSportsPage),
      },
      {
        path: 'games/:id/events/:eventId',
        loadComponent: () => import('./pages/games/games-event.page').then((m) => m.GamesEventPage),
      },
      {
        path: 'games/:id/nocs/:nocId',
        loadComponent: () => import('./pages/games/games-noc.page').then((m) => m.GamesNocPage),
      },
      {
        path: 'games/:id/athletes/:athleteId',
        loadComponent: () => import('./pages/games/games-athlete.page').then((m) => m.GamesAthletePage),
      },
      {
        path: 'games/:id/reports/:kind',
        loadComponent: () => import('./pages/games/games-report.page').then((m) => m.GamesReportPage),
      },
      {
        path: 'horses',
        loadComponent: () => import('./pages/horses/horses.page').then((m) => m.HorsesPage),
      },
      {
        path: 'scouting/search',
        loadComponent: () => import('./pages/scouting/search.page').then((m) => m.TalentSearchPage),
      },
      {
        path: 'scouting/compare',
        loadComponent: () => import('./pages/scouting/compare.page').then((m) => m.ComparePage),
      },
      {
        path: 'scouting/shortlists',
        loadComponent: () => import('./pages/scouting/shortlists.page').then((m) => m.ShortlistsPage),
      },
      {
        path: 'scouting/shortlists/:id',
        loadComponent: () => import('./pages/scouting/shortlists.page').then((m) => m.ShortlistsPage),
      },
      {
        path: 'scouting/requests',
        loadComponent: () => import('./pages/scouting/contact-requests.page').then((m) => m.ContactRequestsPage),
      },
      {
        path: 'scouting/rate',
        loadComponent: () => import('./pages/scouting/rate.page').then((m) => m.RatePage),
      },
      {
        path: 'scouting/record-test',
        loadComponent: () => import('./pages/scouting/record-test.page').then((m) => m.RecordTestPage),
      },
      {
        path: 'scouting/guide',
        loadComponent: () => import('./pages/scouting/rating-guide.page').then((m) => m.RatingGuidePage),
      },
      {
        path: 'scouting/guide/:sport',
        loadComponent: () => import('./pages/scouting/rating-guide.page').then((m) => m.RatingGuidePage),
      },
      {
        path: 'scouting/leagues',
        loadComponent: () =>
          import('./pages/scouting/leagues.page').then((m) => m.ScoutingLeaguesPage),
      },
      {
        path: 'scouting/leagues/:id',
        loadComponent: () =>
          import('./pages/scouting/league-squad.page').then((m) => m.LeagueSquadPage),
      },
      {
        path: 'scouting/organisations/:id',
        loadComponent: () =>
          import('./pages/scouting/organisation.page').then((m) => m.ScoutingOrganisationPage),
      },
    ],
  },

  // Older links land back inside the tab shell so the bottom nav stays up.
  { path: 'competitions/new', redirectTo: 'tabs/competitions/new', pathMatch: 'full' },
  { path: 'competitions/:id/setup', redirectTo: 'tabs/competitions/:id/setup' },
  { path: 'competitions/:id/score', redirectTo: 'tabs/competitions/:id/score' },
  {
    path: 'competitions/:id/teams/:participantId',
    redirectTo: 'tabs/competitions/:id/teams/:participantId',
  },
  {
    path: 'competitions/:id/players/:userId',
    redirectTo: 'tabs/competitions/:id/players/:userId',
  },
  {
    path: 'competitions/:competitionId/fixtures/:fixtureId',
    redirectTo: 'tabs/competitions/:competitionId/fixtures/:fixtureId',
  },
  { path: 'competitions/:id', redirectTo: 'tabs/competitions/:id' },

  { path: '**', redirectTo: 'tabs/competitions' },
];
