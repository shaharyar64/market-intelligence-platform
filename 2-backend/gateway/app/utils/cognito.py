import hmac
import hashlib
import base64


def get_secret_hash(
    username: str,
    client_id: str,
    client_secret: str,
) -> str:
    """
    Cognito SECRET_HASH required for confidential app clients.
    """
    msg = username + client_id
    digest = hmac.new(
        client_secret.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return base64.b64encode(digest).decode()
