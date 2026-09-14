# Media Art Router

A self-hosted artwork resolver for Stremio / AIOMetadata-style clients. It resolves poster, backdrop and logo artwork using the requested TVDB-first density policy, then TMDB, then Metahub, with relaxed-TVDB/TMDB-primary rescue. Posters can receive a configurable bottom status sash.

## PostersPlus sash parity

The three extracted source modules that define the PostersPlus discovery vocabulary and matching methods are carried over verbatim, with only Python import paths adapted for this standalone application:

- `app/core/discovery.py`
- `app/core/awards.py`
- `app/core/festivals.py`

Run `python tools/verify_postersplus_parity.py` to verify the zero-diff parity check against the supplied PostersPlus-dev source path when both projects are available.

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
