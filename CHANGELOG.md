## 2026-09-15

### MDBList show-route fix

- Fixed series/TV keyword lookups to use MDBList's `/show/` route rather than the invalid `/tv/` route.
- Cache normal 400/404 title misses as empty discovery results to avoid repeated noisy warnings and unnecessary upstream calls.
- Bumped the artwork/discovery algorithm version so stale discovery/selection cache entries are not reused.

# Changelog

## 2026-09-15

### PostersPlus parity fixes

- Ported the latest PostersPlus fix that separates movie and TV Golden Globe/Emmy TMDB-id namespaces, preventing movies from wearing TV award sashes when numeric TMDB ids overlap.
- Ported the latest PostersPlus unreleased-movie release-status fix: limited theatrical releases (TMDB release types 2 and 3) count as theatrical, future festival/premiere dates count as evidence that a title is not yet released, and a TMDB `Released` flag only falls back to `Streaming` when there is no future release evidence.
- Legacy movie release-cache rows that lack the new premiere-date field are refreshed once.
- The newer PostersPlus option that prints the upcoming date inside the release-status sash is intentionally not ported.

