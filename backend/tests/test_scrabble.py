"""Official word-entry scoring: tiles, premiums, bingo and remaining racks."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.competitions.models import Competition, Participant
from apps.competitions.scrabble.scoring import apply_endgame, score_move, score_word
from apps.fixtures.models import Fixture, FixtureSide

pytestmark = pytest.mark.django_db


def _word(text, *, letter_mults=None, word_mult=1, blanks=(), news=None, ids=None):
    tiles = []
    for index, char in enumerate(text):
        tile = {
            "letter": char,
            "blank": index in blanks,
            "letter_mult": (letter_mults or {}).get(index, 1),
            "new": True if news is None else news.get(index, True),
        }
        if ids and index in ids:
            tile["id"] = ids[index]
        tiles.append(tile)
    return {"text": text, "tiles": tiles, "word_mult": word_mult}


def test_cat_plain_is_five():
    assert score_word(_word("CAT")) == 5


def test_cat_with_c_on_triple_letter_is_eleven():
    assert score_word(_word("CAT", letter_mults={0: 3})) == 11


def test_cat_on_double_word_is_ten():
    assert score_word(_word("CAT", word_mult=2)) == 10


def test_quiz_q_on_double_letter_and_triple_word_is_96():
    word = _word("QUIZ", letter_mults={0: 2}, word_mult=3)
    assert score_word(word) == 96
    total, bingo = score_move({"type": "play", "words": [word]})
    assert total == 96
    assert bingo is False


def test_blank_as_z_in_quiz_is_12_even_with_a_premium():
    word = _word("QUIZ", letter_mults={3: 3}, blanks={3})
    assert score_word(word) == 12


def test_two_words_share_a_new_premium_tile():
    main = _word("CAT", letter_mults={0: 3}, ids={0: "c"})
    cross = _word("CO", letter_mults={0: 3}, news={0: True, 1: False}, ids={0: "c"})
    total, _ = score_move({"type": "play", "words": [main, cross]})
    assert score_word(main) == 11
    assert score_word(cross) == 10
    assert total == 21


def test_premium_on_an_existing_tile_is_ignored():
    word = _word("CAT", letter_mults={0: 3}, news={0: False, 1: True, 2: True}, word_mult=2)
    # C is already on the board so the triple letter is ignored; the word still uses DW.
    assert score_word(word) == 10


def test_seven_new_tiles_add_fifty_once():
    word = _word("RETAINS")
    total, bingo = score_move({"type": "play", "words": [word]})
    assert bingo is True
    assert total == score_word(word) + 50
    again, _ = score_move({"type": "play", "words": [word, _word("AS", news={0: False, 1: True})]})
    assert again == score_word(word) + score_word(_word("AS", news={0: False, 1: True})) + 50


def test_end_game_rack_adjustment():
    rows = apply_endgame(
        [
            {"side": "ada", "letters": "QST"},
            {"side": "bo", "letters": ""},
        ]
    )
    by_side = {row["side"]: row for row in rows}
    assert by_side["ada"]["unplayed"] == -12
    assert by_side["ada"]["tiles_out"] == 0
    assert by_side["bo"]["unplayed"] == 0
    assert by_side["bo"]["tiles_out"] == 12


def _match(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Club night", "preset": "scrabble", "format": "league"},
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    people = [
        Participant.objects.create(competition=competition, name=name, kind="individual")
        for name in ("Ada", "Bo")
    ]
    fixture = Fixture.objects.create(
        competition=competition, label="Board 1", status=Fixture.Status.LIVE, duration_minutes=25
    )
    sides = [
        FixtureSide.objects.create(fixture=fixture, participant=person, position=index)
        for index, person in enumerate(people)
    ]
    return fixture, sides


def _url(fixture, tail=""):
    return f"/api/v1/competitions/{fixture.competition_id}/fixtures/{fixture.id}/scrabble{tail}"


def test_server_recomputes_the_move_and_rejects_a_ninth_new_tile(api):
    fixture, sides = _match(api)
    body = {
        "side": str(sides[0].id),
        "type": "play",
        "words": [_word("QUIZ", letter_mults={0: 2}, word_mult=3)],
        "total": 1,
    }
    saved = api.post(_url(fixture, "/moves"), body, format="json")
    assert saved.status_code == 201, saved.data
    move = saved.data["moves"][0]
    assert move["total"] == 96
    assert move["bingo"] is False
    fixture.refresh_from_db()
    assert fixture.sides.get(pk=sides[0].id).score == Decimal("96")

    too_many = api.post(
        _url(fixture, "/moves"),
        {"side": str(sides[1].id), "type": "play", "words": [_word("RETAINSY")]},
        format="json",
    )
    assert too_many.status_code == 400
    assert "7" in str(too_many.data)


def test_pass_and_lost_challenge_are_zero_and_racks_close_the_game(api):
    fixture, sides = _match(api)
    api.post(
        _url(fixture, "/moves"),
        {"side": str(sides[0].id), "type": "play", "words": [_word("CAT")]},
        format="json",
    )
    passed = api.post(
        _url(fixture, "/moves"),
        {"side": str(sides[1].id), "type": "pass"},
        format="json",
    )
    assert passed.status_code == 201, passed.data
    assert passed.data["moves"][-1]["total"] == 0

    racks = api.post(
        _url(fixture, "/racks"),
        {
            "racks": [
                {"side": str(sides[0].id), "letters": ""},
                {"side": str(sides[1].id), "letters": "QST"},
            ]
        },
        format="json",
    )
    assert racks.status_code == 200, racks.data
    fixture.recalculate_scores()
    assert fixture.sides.get(pk=sides[0].id).score == Decimal("17")  # 5 + 12 from Bo's rack
    assert fixture.sides.get(pk=sides[1].id).score == Decimal("-12")
