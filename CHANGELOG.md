# Changelog

## 2026-09-15

### PostersPlus parity fixes

- Ported the latest PostersPlus fix that separates movie and TV Golden Globe/Emmy TMDB-id namespaces, preventing movies from wearing TV award sashes when numeric TMDB ids overlap.
- Ported the latest PostersPlus unreleased-movie release-status fix: limited theatrical releases (TMDB release types 2 and 3) count as theatrical, future festival/premiere dates count as evidence that a title is not yet released, and a TMDB `Released` flag only falls back to `Streaming` when there is no future release evidence.
- Legacy movie release-cache rows that lack the new premiere-date field are refreshed once.
- The newer PostersPlus option that prints the upcoming date inside the release-status sash is intentionally not ported.

