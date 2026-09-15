# Artwork Selection Audit

## Requested selection rule

For posters and logos, the router now uses this exact deterministic rule:

1. TVDB first, only when the category contains at least `TVDB_MIN_ARTWORKS` items (or `TVDB_MIN_LOGOS` for logos).
2. Within TVDB: English first, then TMDB-supplied original language.
3. Within a matching language bucket: **take the first artwork returned by TVDB**. No score, votes, popularity, or local quality ranking is applied.
4. TMDB next, with English first and original language second.
5. Within a matching language bucket: **take the first artwork returned by TMDB**. No local scoring/reranking is applied.
6. Metahub by IMDb ID next.
7. If all of the above fail, retry TVDB with the artwork-count gate disabled and use a provider-marked primary artwork when one exists, otherwise the first returned artwork.
8. If that still fails, use TMDB's title-level primary artwork (`poster_path` / `backdrop_path`).

For backdrops, `TEXTLESS_BACKDROPS_ONLY=true` restricts TMDB to language-neutral (`iso_639_1` null/empty) candidates and TVDB to language-neutral artwork. Within that textless bucket, the first API-returned artwork is used.

## Cache invalidation

`ART_SELECTION_ALGORITHM_VERSION=5` is included in the selection-cache key. Changing the artwork selection algorithm therefore bypasses selections made by earlier versions.

## PostersPlus sash parity

The following extracted source modules are byte-for-byte equivalent after only import-path/module-name adaptation:

- `discovery.py`: 0 diff lines
- `awards.py`: 0 diff lines
- `festivals.py`: 0 diff lines

The configurable sash inventory is exact: PostersPlus has 30 slots and Media Art Router has the same 30 slot IDs with no missing or extra slots.
