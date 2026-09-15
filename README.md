# Media Art Router

A self-hosted artwork resolver for Stremio / AIOMetadata-style clients. It resolves poster, backdrop and logo artwork using the requested TVDB-first density policy, then TMDB, then Metahub, with relaxed-TVDB/TMDB-primary rescue. Posters can receive a configurable bottom status sash.

## PostersPlus sash parity

The three extracted source modules that define the PostersPlus discovery vocabulary and matching methods are carried over verbatim, with only Python import paths adapted for this standalone application:

- `app/core/discovery.py`
- `app/core/awards.py`
- `app/core/festivals.py`

Run `python tools/verify_postersplus_parity.py --postersplus /path/to/PostersPlus-dev` to verify the zero-diff parity check against the supplied PostersPlus-dev source checkout.

The 30 configurable PostersPlus sash slots are all present: `wins`, `gg_wins`, `festival`, `pic_noms`, `gg_noms`, `studio`, `director`, `cast`, `trending`, `trending_broad`, `premiere`, `new_release`, `just_added`, `new_season`, `season_finale`, `cult`, `foreign`, `true_story`, `short_film`, `mini_series`, `binge_ready`, `returning`, `airing`, `cancelled`, `ended`, `physical`, `streaming`, `cinema`, `production`.

PostersPlus legacy aliases are also accepted: `structural`, `emmy_noms`, `digital_release`, and `noms`.

`top_rated` is the requested new sash. It uses IMDb's `title.ratings.tsv.gz`, refreshes daily by default, and is controlled by `TOP_RATED_THRESHOLD` (8.5 default) and `TOP_RATED_MIN_VOTES` (500 default).

## AIOMetadata URL templates

```text
https://YOUR-DOMAIN/backdrop/tmdb:{type}:{tmdb_id?}&imdb:{imdb_id?}&tvdb:{tvdb_id?}.jpg
https://YOUR-DOMAIN/poster/tmdb:{type}:{tmdb_id?}&imdb:{imdb_id?}&tvdb:{tvdb_id?}.jpg
https://YOUR-DOMAIN/logo/tmdb:{type}:{tmdb_id?}&imdb:{imdb_id?}&tvdb:{tvdb_id?}.png
```

Blank optional placeholders are treated as missing values. A request can also be resolved from IMDb or TVDB when the TMDB placeholder is blank; this is important for the `?` placeholder behavior used by AIOMetadata.

## Artwork selection

Artwork selection is deliberately deterministic. Within each provider/language bucket, the router takes the first artwork returned by the provider API; it does not rerank posters or logos by vote score, score, popularity, or its own quality heuristic. The selection cache uses `ART_SELECTION_ALGORITHM_VERSION` so changing this policy invalidates prior selections.


Normal selection is:

`TVDB density-qualified -> TMDB -> Metahub -> relaxed TVDB -> TMDB primary`

TVDB normally requires 10+ matching artworks for posters/backdrops and 3+ for logos. For posters/logos, normal TVDB selection is English first and then TMDB's original language. For backdrops with `TEXTLESS_BACKDROPS_ONLY=true`, the provider-neutral/language-free candidate pool is used only; language-bearing backdrop candidates are not admitted to the normal textless path.

## Sash sources

Award/festival matching follows the supplied PostersPlus implementation. Keyword-backed signals use MDBList when `MDBLIST_API_KEY` is set. Custom trending sources accept normal MDBList list-page URLs without an MDBList API key; they are normalized to their `/json` representation and ranked like the PostersPlus implementation. When no custom source is configured, the router uses the TMDB trending endpoint.

The PostersPlus newly-streaming signal is restored through its `r/movieleaks`/Arctic Shift polling model. TMDB release-date logic is also restored for `Just Added`, `Cinema`, `Streaming`, `Physical`, and movie production status, while TV lifecycle status is mapped from the TMDB status/episode metadata exactly through the extracted discovery rules.

## Changing the port

Set `PORT` in `.env`, for example:

```dotenv
PORT=9090
```

Compose maps `${PORT}` on the host to `${PORT}` in the container and Uvicorn/healthcheck use the same value. Then run:

```bash
docker compose up -d
```

## Docker / GHCR

The GitHub Actions workflow builds `linux/amd64` and `linux/arm64` images and publishes them to GHCR. See `SETUP_GITHUB_DESKTOP.md` for a beginner-friendly Windows GitHub Desktop -> GitHub -> GHCR -> Linux Docker Compose walkthrough.

## Cache directory permissions

The image starts as root only long enough to create/chown the bind-mounted cache directory, then drops to the unprivileged `appuser` (UID 10001). This avoids the common `sqlite3.OperationalError: unable to open database file` failure when Docker creates `./cache` as root on the host. `CACHE_HOST_PATH` may be changed in `.env` if you want the persistent cache elsewhere.

If your Docker host uses a filesystem that prevents root from changing ownership (for example some root-squashed network mounts), create the directory yourself and grant UID 10001 access before starting:

```bash
mkdir -p ./cache
sudo chown -R 10001:10001 ./cache
```

### Existing deployment showing `unable to open database file`

That error means the SQLite file's parent directory is not writable by the container user. Pull the updated image (or rebuild the updated repository) after applying the new `entrypoint.sh`; it now fixes ownership automatically at startup. For an existing host cache, this one-time command is also safe and immediate:

```bash
cd /opt/mediaart-router
mkdir -p ./cache
sudo chown -R 10001:10001 ./cache
docker compose down
docker compose pull
docker compose up -d
```

If you use another `CACHE_HOST_PATH`, substitute that directory. Do not delete the cache unless you specifically want to lose cached artwork/metadata and local IMDb data.

### Sash visual profile

The default sash profile intentionally follows the supplied inspiration: labels are
uppercase, the tab width is a fixed 35% of the poster width, and all labels share one
font size and fixed baseline. Label length only changes horizontal fitting, never sash
geometry or vertical placement.


Sash typography uses Roboto Condensed Bold under Apache License 2.0; the license text is included in `app/assets/ROBOTO-APACHE-2.0.txt`.
