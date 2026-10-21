"""Competition conversation: who can take part, and photos and videos on posts and comments."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.media_assets.models import MediaAsset

User = get_user_model()


def client_for(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def ready_image(owner, competition=None) -> MediaAsset:
    return MediaAsset.objects.create(
        owner=owner,
        competition=competition,
        kind=MediaAsset.Kind.IMAGE,
        status=MediaAsset.Status.READY,
        storage_provider="local",
        storage_key=f"images/{owner.id}/photo.jpg",
    )


def ready_video(owner, competition=None) -> MediaAsset:
    return MediaAsset.objects.create(
        owner=owner,
        competition=competition,
        kind=MediaAsset.Kind.VIDEO,
        status=MediaAsset.Status.READY,
        playback_url="https://videos.example.com/clip.mp4",
    )


@pytest.fixture
def outsider(db):
    return User.objects.create_user(email="outsider@example.com", password="pw-123456789")


@pytest.fixture
def post_id(api, competition) -> str:
    response = api.post(
        f"/api/v1/competitions/{competition.id}/posts", {"body": "Kick-off!"}, format="json"
    )
    assert response.status_code == 201
    return response.data["id"]


def test_creating_a_post_returns_the_full_post_with_media(api, competition, user):
    image = ready_image(user, competition)
    video = ready_video(user, competition)

    response = api.post(
        f"/api/v1/competitions/{competition.id}/posts",
        {"body": "Match day", "media_asset_ids": [str(image.id), str(video.id)]},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["author"]["id"] == str(user.id)
    kinds = [item["media_asset"]["kind"] for item in response.data["media"]]
    assert kinds == ["image", "video"]
    assert response.data["media"][0]["media_asset"]["url"].endswith(image.storage_key)


def test_a_comment_can_carry_photos_and_videos(api, user, competition, post_id):
    image = ready_image(user, competition)
    video = ready_video(user, competition)

    response = api.post(
        f"/api/v1/posts/{post_id}/comments",
        {"body": "", "media_asset_ids": [str(image.id), str(video.id)]},
        format="json",
    )

    assert response.status_code == 201, response.data
    assert [m["media_asset"]["kind"] for m in response.data["media"]] == ["image", "video"]

    listed = api.get(f"/api/v1/posts/{post_id}/comments")
    assert len(listed.data["results"][0]["media"]) == 2


def test_an_empty_comment_is_rejected(api, post_id):
    response = api.post(f"/api/v1/posts/{post_id}/comments", {"body": "  "}, format="json")
    assert response.status_code == 400


def test_replies_are_listed_under_their_comment(api, post_id):
    parent = api.post(f"/api/v1/posts/{post_id}/comments", {"body": "Top"}, format="json")
    reply = api.post(
        f"/api/v1/posts/{post_id}/comments",
        {"body": "Reply", "parent": parent.data["id"]},
        format="json",
    )
    assert reply.status_code == 201

    top_level = api.get(f"/api/v1/posts/{post_id}/comments")
    assert [c["body"] for c in top_level.data["results"]] == ["Top"]
    assert top_level.data["results"][0]["reply_count"] == 1

    replies = api.get(f"/api/v1/posts/{post_id}/comments", {"parent": parent.data["id"]})
    assert [c["body"] for c in replies.data["results"]] == ["Reply"]


def test_a_comment_cannot_attach_someone_elses_media(api, competition, other_user, post_id):
    foreign = ready_image(other_user, competition)
    response = api.post(
        f"/api/v1/posts/{post_id}/comments",
        {"body": "Mine now", "media_asset_ids": [str(foreign.id)]},
        format="json",
    )
    assert response.status_code == 400


def test_media_uploaded_to_another_competition_is_rejected(api, user, competition, post_id):
    elsewhere = Competition.objects.create(name="Elsewhere", owner=user)
    stray = ready_image(user, elsewhere)

    response = api.post(
        f"/api/v1/posts/{post_id}/comments",
        {"body": "Wrong place", "media_asset_ids": [str(stray.id)]},
        format="json",
    )
    assert response.status_code == 400


def test_a_photo_that_is_still_uploading_cannot_be_attached(api, user, competition):
    pending = MediaAsset.objects.create(
        owner=user, competition=competition, kind=MediaAsset.Kind.IMAGE
    )
    response = api.post(
        f"/api/v1/competitions/{competition.id}/posts",
        {"body": "Soon", "media_asset_ids": [str(pending.id)]},
        format="json",
    )
    assert response.status_code == 400


def test_at_most_four_attachments(api, user, competition, post_id):
    images = [str(ready_image(user, competition).id) for _ in range(5)]
    response = api.post(
        f"/api/v1/posts/{post_id}/comments",
        {"body": "Gallery", "media_asset_ids": images},
        format="json",
    )
    assert response.status_code == 400


def test_outsiders_can_read_a_public_feed_but_not_comment(competition, outsider, post_id):
    client = client_for(outsider)

    assert client.get(f"/api/v1/competitions/{competition.id}/posts").status_code == 200
    assert client.get(f"/api/v1/posts/{post_id}/comments").status_code == 200

    comment = client.post(f"/api/v1/posts/{post_id}/comments", {"body": "Hi"}, format="json")
    assert comment.status_code == 403

    react = client.post(
        f"/api/v1/competitions/{competition.id}/posts/{post_id}/react",
        {"kind": "like"},
        format="json",
    )
    assert react.status_code == 403

    detail = client.get(f"/api/v1/competitions/{competition.id}")
    assert detail.data["can_post"] is False


def test_rostered_players_and_team_managers_take_part(competition, outsider, post_id):
    team = Participant.objects.create(competition=competition, name="Harbour Hawks")
    RosterMember.objects.create(participant=team, name="Outsider", user=outsider)
    client = client_for(outsider)

    assert client.get(f"/api/v1/competitions/{competition.id}").data["can_post"] is True
    comment = client.post(
        f"/api/v1/posts/{post_id}/comments", {"body": "Let's go Hawks"}, format="json"
    )
    assert comment.status_code == 201

    manager = User.objects.create_user(email="manager@example.com", password="pw-123456789")
    Participant.objects.create(competition=competition, name="Owls", managed_by=manager)
    posted = client_for(manager).post(
        f"/api/v1/competitions/{competition.id}/posts", {"body": "Owls ready"}, format="json"
    )
    assert posted.status_code == 201


def test_private_feeds_are_hidden_from_outsiders(competition, outsider, post_id):
    competition.is_private = True
    competition.save(update_fields=["is_private"])

    client = client_for(outsider)
    assert client.get(f"/api/v1/competitions/{competition.id}/posts").status_code == 404
    assert client.get(f"/api/v1/posts/{post_id}/comments").status_code == 404


def test_only_the_author_or_an_admin_deletes_a_comment(api, competition, other_user, post_id):
    from apps.competitions.models import Membership
    from apps.core.permissions import Role

    Membership.objects.create(competition=competition, user=other_user, role=Role.MEMBER)
    mine = api.post(f"/api/v1/posts/{post_id}/comments", {"body": "Owner says"}, format="json")
    theirs = client_for(other_user).post(
        f"/api/v1/posts/{post_id}/comments", {"body": "Member says"}, format="json"
    )

    blocked = client_for(other_user).delete(f"/api/v1/posts/{post_id}/comments/{mine.data['id']}")
    assert blocked.status_code == 403

    # The owner moderates.
    removed = api.delete(f"/api/v1/posts/{post_id}/comments/{theirs.data['id']}")
    assert removed.status_code == 204
    feed = api.get(f"/api/v1/competitions/{competition.id}/posts")
    assert feed.data["results"][0]["comment_count"] == 1


def test_local_uploads_store_bytes_and_finish(api, competition, settings, tmp_path):
    settings.LOCAL_MEDIA_UPLOADS = True
    settings.MEDIA_ROOT = tmp_path

    target = api.post(
        "/api/v1/media/request-upload",
        {
            "kind": "image",
            "filename": "goal.png",
            "content_type": "image/png",
            "size_bytes": 4,
            "competition_id": str(competition.id),
        },
        format="json",
    )
    assert target.status_code == 201
    assert target.data["method"] == "PUT"
    upload_path = target.data["upload_url"].split("testserver", 1)[1]

    anon = APIClient()
    stored = anon.generic("PUT", upload_path, b"\x89PNG", content_type="image/png")
    assert stored.status_code == 200
    assert (tmp_path / target.data["storage_key"]).read_bytes() == b"\x89PNG"

    asset_id = target.data["media_asset"]["id"]
    done = api.post(f"/api/v1/media/{asset_id}/complete", {}, format="json")
    assert done.status_code == 200
    assert done.data["status"] == "ready"
    assert done.data["url"].endswith(target.data["storage_key"])

    # The link only works once and only with its own token.
    again = anon.generic("PUT", upload_path, b"more", content_type="image/png")
    assert again.status_code == 404
    forged = anon.generic(
        "PUT", f"/api/v1/media/{asset_id}/local-upload?token=nope", b"x", content_type="image/png"
    )
    assert forged.status_code == 403


def test_local_video_uploads_are_ready_once_stored(api, competition, settings, tmp_path):
    settings.LOCAL_MEDIA_UPLOADS = True
    settings.MEDIA_ROOT = tmp_path

    target = api.post(
        "/api/v1/media/request-upload",
        {
            "kind": "video",
            "filename": "try.mp4",
            "content_type": "video/mp4",
            "competition_id": str(competition.id),
        },
        format="json",
    )
    assert target.status_code == 201
    upload_path = target.data["upload_url"].split("testserver", 1)[1]
    assert (
        APIClient().generic("PUT", upload_path, b"mp4", content_type="video/mp4").status_code == 200
    )

    asset = MediaAsset.objects.get(pk=target.data["media_asset"]["id"])
    assert asset.status == MediaAsset.Status.READY
    assert asset.url.endswith(asset.storage_key)


def test_local_uploads_are_off_unless_enabled(api, settings):
    settings.LOCAL_MEDIA_UPLOADS = False
    asset = ready_image(User.objects.first())
    response = APIClient().generic(
        "PUT", f"/api/v1/media/{asset.id}/local-upload?token=x", b"x", content_type="image/png"
    )
    assert response.status_code == 403


def test_discover_feed_lists_public_posts_with_league_name(api, competition, user):
    image = ready_image(user, competition)
    created = api.post(
        f"/api/v1/competitions/{competition.id}/posts",
        {"body": "Discover me", "media_asset_ids": [str(image.id)]},
        format="json",
    )
    assert created.status_code == 201

    listed = api.get("/api/v1/discover/posts")
    assert listed.status_code == 200
    match = next(row for row in listed.data["results"] if row["id"] == created.data["id"])
    assert match["competition_name"] == competition.name
    assert match["media"][0]["media_asset"]["kind"] == "image"

    media_only = api.get("/api/v1/discover/posts", {"has_media": "true"})
    assert any(row["id"] == created.data["id"] for row in media_only.data["results"])


def test_a_written_post_is_from_a_personal_profile(api, competition, user):
    user.headline = "Centre-back · Testing football"
    user.city = "Johannesburg"
    user.save(update_fields=["headline", "city"])
    response = api.post(
        f"/api/v1/competitions/{competition.id}/posts",
        {"body": "From my profile"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["kind"] == "profile"
    assert response.data["author"]["headline"] == "Centre-back · Testing football"
    assert response.data["author"]["city"] == "Johannesburg"
    assert response.data["competition_name"] == competition.name


def test_live_match_events_become_feed_posts(competition, user, rugby_scoring, participants):
    from apps.competitions.models import RosterMember
    from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent
    from apps.social.live import publish_full_time, publish_kickoff, publish_score_event
    from apps.social.models import Post

    home, away = participants[0], participants[1]
    fixture = Fixture.objects.create(
        competition=competition,
        status=Fixture.Status.LIVE,
        label="Round 1",
        duration_minutes=80,
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, score=0)
    FixtureSide.objects.create(fixture=fixture, participant=away, score=0)
    player = RosterMember.objects.create(
        participant=home, name="Carmen Adams", number=9, user=user
    )
    event = ScoreEvent.objects.create(
        fixture=fixture,
        side=home_side,
        scoring_category=rugby_scoring["try"],
        player=player,
        player_name="Carmen Adams",
        minute=12,
        recorded_by=user,
        quantity=1,
    )
    home_side.score = 5
    home_side.save(update_fields=["score"])

    kickoff = publish_kickoff(fixture)
    scored = publish_score_event(event)
    fixture.status = Fixture.Status.COMPLETED
    fixture.save(update_fields=["status"])
    full_time = publish_full_time(fixture)

    assert kickoff is not None and kickoff.kind == Post.Kind.LIVE
    assert "Kick-off" in kickoff.body
    assert scored.author_id == user.id
    assert "Carmen Adams" in scored.body
    assert "Try" in scored.body
    assert full_time is not None and "Full time" in full_time.body
    assert Post.objects.filter(kind=Post.Kind.LIVE, competition=competition).count() == 3
    assert publish_score_event(event).id == scored.id


def test_discover_feed_hides_private_league_posts(api, competition, outsider, post_id):
    competition.is_private = True
    competition.save(update_fields=["is_private"])

    hidden = client_for(outsider).get("/api/v1/discover/posts")
    assert hidden.status_code == 200
    assert all(row["id"] != post_id for row in hidden.data["results"])

    visible = api.get("/api/v1/discover/posts")
    assert any(row["id"] == post_id for row in visible.data["results"])
