# Final Requirements Audit

Audited against the original Media Art Router request and the supplied PostersPlus-dev source.

## Artwork routing

- AIOMetadata-style `/poster/...`, `/backdrop/...`, `/logo/...` paths: implemented.
- `{type}` movie/series handling: implemented; series aliases are accepted internally as TV.
- Optional blank IDs produced by AIOMetadata's `?` placeholders: blank values are parsed as missing, not treated as literal IDs.
- Provider order: TVDB density-qualified -> TMDB -> Metahub -> relaxed TVDB -> TMDB primary.
- TVDB thresholds: posters/backdrops 10+, logos 3+ by default and configurable.
- TVDB language order: English then TMDB-supplied original language, with duplicates removed.
- TMDB language order: English then original language, with a second image query when the original language was not present initially.
- Backdrop textless-only mode: enabled by default and configurable.
- Final fallback: relaxed TVDB and TMDB primary artwork.
- Metahub poster/background/logo public URL patterns: implemented.

## Sashes

All 30 configurable PostersPlus sash slots are present, with the same slot IDs and labels from `configurator.html`:

`wins`, `gg_wins`, `festival`, `pic_noms`, `metacritic`, `gg_noms`, `trending`, `trending_broad`, `premiere`, `new_release`, `just_added`, `new_season`, `season_finale`, `studio`, `director`, `cast`, `cult`, `foreign`, `true_story`, `short_film`, `mini_series`, `binge_ready`, `returning`, `airing`, `cancelled`, `ended`, `physical`, `streaming`, `cinema`, `production`.

Also present: PostersPlus legacy aliases `structural`, `emmy_noms`, `digital_release`, `noms`; and new `top_rated`.

The supplied PostersPlus `discovery.py`, `awards.py`, and `festivals.py` were compared after only adapting standalone import paths. All three are zero-diff identical.

The digital-release signal retains the PostersPlus method: Arctic Shift archive -> `r/movieleaks`, 1-day trust delay by default, 30-day window, IMDb ID extraction from title/body/URL, timestamp pagination, 100 posts/page, 10-page cap, 1-second page delay, daily polling, and cache pruning.

Custom MDBList list URLs are normalized to their `/json` form without requiring an MDBList API key for the list itself. The ranking is the source list order/rank.

TMDB release-date facts power `Just Added`, `Cinema`, `Streaming`, `Physical`, and movie `Production`; TV lifecycle facts power `Airing`, `Returning`, `Ended`, and `Cancelled`. The same extracted PostersPlus discovery rules are used to evaluate the resulting facts.

New Top Rated sash: IMDb `title.ratings.tsv.gz`, configurable 8.5 threshold, configurable minimum votes, default 24-hour refresh.

Sash priority is fully configurable through `SASH_PRIORITY`.

## Rendering

- Bottom rail with centered raised rounded tab: implemented.
- Inter Bold font bundled.
- Poster-derived colour with saturation/skin suppression and dark-poster neutral gray handling.
- Configurable sash geometry and dark-poster behavior via `.env`.

## Configuration

`.env` controls API credentials, image sizes, port, cache locations and TTLs, TVDB thresholds, textless behavior, Top Rated settings, concurrency/resource limits, timeouts, trending sources, digital-release windows, cinema window, sash rendering, sash priority, and access key.

## Reliability

- Same-key request coalescing prevents duplicate concurrent resolution work.
- HTTP connection pooling and upstream concurrency semaphore are configurable.
- Image-processing concurrency is configurable.
- Persistent file cache plus SQLite state cache.
- Graceful lifespan shutdown cancels background jobs and closes HTTP/SQLite resources.
- Single Uvicorn worker is intentional so request coalescing remains process-wide.

## Docker

- Port is configurable through `PORT` and used consistently by Uvicorn, Compose, and healthcheck.
- Cache bind mount is configurable with `CACHE_HOST_PATH`.
- Container starts as root only long enough to ensure the mounted cache is writable, then drops to UID 10001 `appuser`.
- This fixes the common `sqlite3.OperationalError: unable to open database file` failure caused by Docker creating `./cache` as root.
- GitHub Actions publishes multi-architecture GHCR images.
