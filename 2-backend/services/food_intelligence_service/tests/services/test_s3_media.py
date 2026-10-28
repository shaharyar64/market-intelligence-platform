from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError


def test_resolve_image_key_returns_key_when_object_exists(mock_settings):
    from services.food_intelligence_service.app.services import s3_media

    fake_client = MagicMock()
    fake_client.head_object.return_value = {}

    with patch.object(s3_media, "_client", return_value=fake_client):
        ref = s3_media.resolve_image_key("instagram", "DbJF0VDDvRO")

    assert ref == "media/instagram/DbJF0VDDvRO.jpg"
    fake_client.head_object.assert_called_once_with(Bucket="raw-data-bucket", Key="media/instagram/DbJF0VDDvRO.jpg")


def test_resolve_image_key_returns_none_when_object_missing(mock_settings):
    from services.food_intelligence_service.app.services import s3_media

    fake_client = MagicMock()
    fake_client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")

    with patch.object(s3_media, "_client", return_value=fake_client):
        ref = s3_media.resolve_image_key("instagram", "missing_post")

    assert ref is None


def test_presigned_url_delegates_to_boto(mock_settings):
    from services.food_intelligence_service.app.services import s3_media

    fake_client = MagicMock()
    fake_client.generate_presigned_url.return_value = "https://signed-url"

    with patch.object(s3_media, "_client", return_value=fake_client):
        url = s3_media.presigned_url("media/instagram/x.jpg", expires_in=900)

    assert url == "https://signed-url"
    fake_client.generate_presigned_url.assert_called_once_with(
        "get_object", Params={"Bucket": "raw-data-bucket", "Key": "media/instagram/x.jpg"}, ExpiresIn=900,
    )


def test_resolve_image_key_returns_none_on_access_denied(mock_settings):
    from botocore.exceptions import ClientError

    from services.food_intelligence_service.app.services import s3_media

    denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}, "HeadObject")
    with patch.object(s3_media, "_client") as mock_client:
        mock_client.return_value.head_object.side_effect = denied
        assert s3_media.resolve_image_key("instagram", "p1") is None


def test_resolve_image_key_still_raises_on_unexpected_error(mock_settings):
    import pytest
    from botocore.exceptions import ClientError

    from services.food_intelligence_service.app.services import s3_media

    throttled = ClientError({"Error": {"Code": "SlowDown", "Message": "throttled"}}, "HeadObject")
    with patch.object(s3_media, "_client") as mock_client:
        mock_client.return_value.head_object.side_effect = throttled
        with pytest.raises(ClientError):
            s3_media.resolve_image_key("instagram", "p1")
