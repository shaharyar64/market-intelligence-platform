import boto3
from gateway.app.core.config import get_settings

settings = get_settings()


def get_cognito_client():
    return boto3.client(
        "cognito-idp",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
