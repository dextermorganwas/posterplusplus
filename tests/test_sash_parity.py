import json, subprocess, sys
from pathlib import Path

from app.config import settings
from app.core.discovery import ALL_PRIORITY_SLOTS, DiscoveryMeta, pick_sash
from app.core.sash_inventory import POSTERSPLUS_SASH_SLOTS

PP_SASH_SLOTS = [slot for slot, _label in POSTERSPLUS_SASH_SLOTS]


def test_every_configurable_postersplus_sash_slot_exists():
    missing = [x for x in PP_SASH_SLOTS if x not in ALL_PRIORITY_SLOTS]
    assert not missing, missing


def test_postersplus_legacy_slots_are_still_supported():
    for slot in ("structural", "emmy_noms", "digital_release", "noms"):
        assert slot in ALL_PRIORITY_SLOTS


def test_each_sash_slot_can_be_selected_from_matching_meta():
    cases = {
        "wins": DiscoveryMeta(award_wins=["Oscar Winner"]),
        "gg_wins": DiscoveryMeta(award_wins=["Globe Winner"]),
        "pic_noms": DiscoveryMeta(award_noms=["Oscar Nominee"]),
        "gg_noms": DiscoveryMeta(award_noms=["Globe Nominee"]),
        "festival": DiscoveryMeta(festival_label="Cannes Winner"),
        "studio": DiscoveryMeta(matched_studios=["A24 Films"]),
        "director": DiscoveryMeta(matched_directors=["C. Nolan"]),
        "cast": DiscoveryMeta(matched_cast=["Cate Blanchett"]),
        "trending": DiscoveryMeta(trending_rank=1),
        "trending_broad": DiscoveryMeta(trending_rank=41),
        "premiere": DiscoveryMeta(is_premiere=True),
        "new_release": DiscoveryMeta(is_new_release=True),
        "just_added": DiscoveryMeta(is_just_added=True),
        "new_season": DiscoveryMeta(is_new_season=True),
        "season_finale": DiscoveryMeta(is_season_finale=True),
        "cult": DiscoveryMeta(is_cult=True),
        "foreign": DiscoveryMeta(original_language="fr"),
        "true_story": DiscoveryMeta(is_true_story=True),
        "short_film": DiscoveryMeta(is_short_film=True),
        "mini_series": DiscoveryMeta(is_mini_series=True),
        "binge_ready": DiscoveryMeta(is_binge_ready=True),
        "returning": DiscoveryMeta(is_returning=True),
        "airing": DiscoveryMeta(release_status="Airing"),
        "cancelled": DiscoveryMeta(release_status="Cancelled"),
        "ended": DiscoveryMeta(release_status="Ended"),
        "physical": DiscoveryMeta(release_status="Physical"),
        "streaming": DiscoveryMeta(release_status="Streaming"),
        "cinema": DiscoveryMeta(release_status="Cinema"),
        "production": DiscoveryMeta(release_status="Production"),
    }
    for slot, meta in cases.items():
        picked = pick_sash(meta, [slot])
        assert picked is not None, slot


def test_wins_and_nomination_split_matches_postersplus():
    meta = DiscoveryMeta(award_wins=["Oscar Winner", "Globe Winner"], award_noms=["Oscar Nominee", "Globe Nominee"])
    assert pick_sash(meta, ["wins"]) == ("Oscar Winner", "win")
    assert pick_sash(meta, ["gg_wins"]) == ("Globe Winner", "win")
    assert pick_sash(meta, ["pic_noms"]) == ("Oscar Nominee", "nom")
    assert pick_sash(meta, ["gg_noms"]) == ("Globe Nominee", "nom")
