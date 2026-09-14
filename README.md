# Media Art Router

A self-hosted artwork resolver for Stremio / AIOMetadata-style clients. It resolves poster, backdrop, and logo artwork using a TVDB-first density-aware selection policy, then TMDB, then Metahub, with a final TVDB/TMDB primary-art rescue. Posters can also receive a bottom status sash.

## Attribution / license

The `app/core/awards.py`, `app/core/discovery.py`, and `app/core/festivals.py` files are derived from the uploaded PostersPlus project by UmbraProjects and are retained under its AGPL-3.0-or-later license. The sash source vocabulary and award/festival matching logic are intentionally based on that project. See `LICENSE`.

## AIOMetadata URL templates

Use exactly the style you described:

```text
https://YOUR-DOMAIN/backdrop/tmdb:{type}:{tmdb_id?}&imdb:{imdb_id?}&tvdb:{tvdb_id?}.jpg
https://YOUR-DOMAIN/poster/tmdb:{type}:{tmdb_id?}&imdb:{imdb_id?}&tvdb:{tvdb_id?}.jpg
https://YOUR-DOMAIN/logo/tmdb:{type}:{tmdb_id?}&imdb:{imdb_id?}&tvdb:{tvdb_id?}.png
```

The router treats blank optional placeholders as missing values.

## Notes

TVDB artwork density is checked per asset category before normal TVDB selection: posters/backdrops default to 10+, logos 3+. If TMDB/Metahub cannot supply an asset, the resolver retries TVDB with the density gate bypassed so a rare title can still get art.

Backdrops are restricted to provider-neutral/textless candidates when `TEXTLESS_BACKDROPS_ONLY=true`. TVDB v4 does not expose the same `iso_639_1=null` signal as TMDB for textlessness, so this version treats TVDB background artwork as eligible artwork and leaves OCR rejection as a future hardening option.

IMDb `title.ratings.tsv.gz` is refreshed daily by default and titles at 8.5+ with at least 500 votes are eligible for the `Top Rated` sash.
