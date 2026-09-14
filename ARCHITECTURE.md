# Architecture and selection policy

## Artwork selection

For posters and logos:

1. Resolve a TVDB numeric ID from the explicit TVDB ID, IMDb ID, or TMDB ID.
2. Fetch the TVDB artwork index and count the matching category.
3. Only let TVDB win the normal race when the category reaches `TVDB_MIN_ARTWORKS` (10 by default) or `TVDB_MIN_LOGOS` (3 by default for logos).
4. Within TVDB, prefer requested language, then English, then original language, then neutral/provider-score ordering.
5. If TVDB does not qualify, use TMDB with the same language idea.
6. If neither provider yields an asset, try Metahub when an IMDb ID exists.
7. If still empty, retry TVDB with the density gate disabled.
8. Finally, use TMDB primary artwork.

For backdrops, the normal selection filters TMDB to language-neutral (`iso_639_1=null` / empty) assets when `TEXTLESS_BACKDROPS_ONLY=true`. TVDB v4 does not expose the identical TMDB language-neutral marker; TVDB backgrounds are therefore selected by artwork type and language. A future OCR gate can make that stricter.

## Request coalescing

All identical selection requests share one asyncio task. Ten simultaneous requests for the same item do not start ten independent upstream fetches. A persistent file cache stores selected metadata, trending snapshots, and fetched art.

The service intentionally runs one Uvicorn worker in Compose/Docker. That makes the in-flight coalescing effective process-wide. Running multiple workers is possible, but each worker would have its own in-memory in-flight table.

## Sash logic

The award/festival/discovery vocabulary and matching logic are derived from the uploaded PostersPlus source. The project is retained under AGPL-3.0-or-later and the source attribution is explicit in the repository.

The new `Top Rated` sash is sourced from IMDb's public ratings dataset and treats `8.5+` as the cutoff. The minimum vote guard is 500 by default in the current prototype; change the code/env when you want a stricter or looser definition.

## Colour algorithm

The sash colour is derived from the poster itself rather than from the sash category. The algorithm samples most of the poster, quantizes it to a small palette, weights saturated/representative colors, suppresses obvious skin-tone candidates, then normalizes the selected hue/value so the label remains legible. Very dark posters can force a neutral dark gray sash. Text switches to black only for a sufficiently light sash color.
