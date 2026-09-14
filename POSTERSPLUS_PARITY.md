# PostersPlus sash parity audit

Configured sash slots found in PostersPlus: **30**.

| # | Slot | PostersPlus label | Implemented |
|---:|---|---|---|
| 1 | `wins` | Best Picture / Major Emmy Win | ✅ |
| 2 | `gg_wins` | Major Golden Globe Win | ✅ |
| 3 | `festival` | Festival Winner | ✅ |
| 4 | `pic_noms` | Best Picture / Major Emmy Nom | ✅ |
| 5 | `metacritic` | Metacritic Must-See | ✅ |
| 6 | `gg_noms` | Major Golden Globe Nom | ✅ |
| 7 | `trending` | TMDB Trending Top {{TRENDING_FETCH_COUNT}} | ✅ |
| 8 | `trending_broad` | TMDB Trending {{TRENDING_FETCH_COUNT_PLUS_ONE}}-{{TRENDING_BROAD_FETCH_COUNT}} | ✅ |
| 9 | `premiere` | Premiere | ✅ |
| 10 | `new_release` | Newly Streaming (New) | ✅ |
| 11 | `just_added` | Just Added | ✅ |
| 12 | `new_season` | New Season | ✅ |
| 13 | `season_finale` | Season Finale | ✅ |
| 14 | `studio` | Notable Studio Name | ✅ |
| 15 | `director` | Notable Director Name | ✅ |
| 16 | `cast` | Notable Cast Name | ✅ |
| 17 | `cult` | Cult Classic | ✅ |
| 18 | `foreign` | Foreign Language | ✅ |
| 19 | `true_story` | True Story | ✅ |
| 20 | `short_film` | Short Film | ✅ |
| 21 | `mini_series` | Miniseries | ✅ |
| 22 | `binge_ready` | Binge Ready | ✅ |
| 23 | `returning` | Returning | ✅ |
| 24 | `airing` | Airing | ✅ |
| 25 | `cancelled` | Cancelled | ✅ |
| 26 | `ended` | Ended | ✅ |
| 27 | `physical` | Physical | ✅ |
| 28 | `streaming` | Streaming | ✅ |
| 29 | `cinema` | Cinema | ✅ |
| 30 | `production` | Production | ✅ |

The generated `app/core/discovery.py`, `app/core/awards.py`, and `app/core/festivals.py` were compared against the supplied source after only adapting standalone import paths. Each produced a zero-line diff.

The digital-release polling algorithm follows PostersPlus: Arctic Shift `r/movieleaks`, 1-day trust delay by default, 30-day window by default, IMDb ID extraction from title/body/URL, timestamp pagination, 100 posts/page, 10-page cap, 1-second page pause, daily polling, and pruning.

The TMDB release-date logic follows PostersPlus for Just Added / Cinema / Streaming / Physical / Production. The TMDB release-status fact retrieval is kept in a standalone provider module so the router can use the same fact source without importing the entire PostersPlus application.
