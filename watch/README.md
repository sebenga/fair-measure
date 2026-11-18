# Referee watch mode

Ship order: **watch PWA first**, native apps later. The PWA runs on Wear OS browsers, Galaxy Watch browsers, and any phone strapped to a wrist.

## PWA (shipped)

- Route: `/ref/watch/:matchId`
- Pairing: on the phone, the referee opens the match and calls `POST /api/v1/competitions/:id/fixtures/:fixtureId/watch/pair` (or taps **Pair watch** when wired in the match UI). That returns a **6-digit code** and a device token. The watch claims with `POST /api/v1/fixtures/:fixtureId/watch/claim`.
- Tokens are match-scoped, expire after the match window, and are revocable (`WatchDeviceToken.revoked_at`).
- Actions are tagged `source=watch`. Offline events queue in IndexedDB with client UUIDs and sync via `POST /api/v1/fixtures/:fixtureId/watch/sync` (server dedupes by `client_uuid`).
- Haptics: Vibration API on period end and card entry. Screen Wake Lock keeps the display on when the browser allows it.
- Layout: high-contrast, large tap targets for round/square faces.

### Assistant watches

Assistants can pair with limited categories later (offside / foul note / sub request). The centre referee still confirms score and discipline.

## Native apps (scaffold only — do not block release)

| Platform | Stack | Notes |
| --- | --- | --- |
| Wear OS | Kotlin + Compose for Wear OS | Same REST sync + event schema as the PWA |
| Apple Watch | SwiftUI watchOS companion via WatchConnectivity | Phone holds the session; watch sends events |

Optional (opt-in, POPIA consent): heart-rate / distance saved as referee fitness data — not required for match control.

## Manual offline test

1. Pair the watch, go live, enable airplane mode.
2. Record Home+/Away+ for a full half.
3. Reconnect — sync indicator goes green, standings/score match, **no duplicate** events (`client_uuid`).
