# Changelog

## v21

- Fixed MDBList discovery failure handling so normal 400/404 responses are silent and cached.
- Added stale-keyword fallback for transient MDBList/network/JSON failures.
- Parallelized independent sash discovery work (MDBList, trending, release info) instead of running it serially.
- Stopped waiting on the IMDb Top Rated dataset refresh in the poster request path.
- Added startup background warming for IMDb ratings and movie/TV trending snapshots.
- Added persistent rendered-sash cache, including no-sash renders, to avoid repeating expensive discovery work for repeat poster requests.
- Coalesced movie release-date work by sharing the same release-info request when multiple release-related sash slots are enabled.
- Kept the latest PostersPlus release/award fixes and sash decision logic intact.
