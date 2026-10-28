from shared.exceptions import ForbiddenException


def is_admin(user: dict) -> bool:
    return "Admins" in user.get("cognito:groups", [])


def authorize_service_access(
    user: dict,
    service_name: str,
    allowed_services: set[str],
):
    if is_admin(user):
        return

    if service_name not in allowed_services:
        raise ForbiddenException("Access denied to service")
