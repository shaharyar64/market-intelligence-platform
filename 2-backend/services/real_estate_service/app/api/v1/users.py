from fastapi import APIRouter, Depends, HTTPException, status
from services.real_estate_service.app.services.cognito import CognitoService
from services.real_estate_service.app.api.deps import get_cognito_service, get_current_active_user, require_admin
from services.real_estate_service.app.models.schemas import (
    CreateUserRequest,
    CreateUserResponse,
    UpdateUserRequest,
    UserResponse,
    UserListResponse,
    MessageResponse
)
from services.real_estate_service.app.utils.exceptions import CognitoException, UserNotFoundException

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=CreateUserResponse, status_code=201)
async def create_user(
    user: CreateUserRequest,
    cognito: CognitoService = Depends(get_cognito_service),
    admin: dict = Depends(require_admin)
):
    """
    Admin endpoint to create a new user with temporary password and assign group
    """
    try:
        result = cognito.create_user(user.email, user.temporary_password, user.role.value, user.name)
        return CreateUserResponse(
            message="User created successfully",
            name=user.name,
            username=result['User']['Username'],
            role=user.role.value,
            status=result['User']['UserStatus']
        )
    except CognitoException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all users (Admin only)",
    description="Get list of all users in the system"
)
async def list_users(
    cognito: CognitoService = Depends(get_cognito_service),
    admin: dict = Depends(require_admin)
):
    try:
        raw_users = cognito.list_users_by_groups()

        users = []
        for user in raw_users:
            user_info = {
                'username': user['Username'],
                'status': user['UserStatus'],
                'enabled': user['Enabled'],
                'created_date': user['UserCreateDate'].isoformat(),
                'modified_date': user['UserLastModifiedDate'].isoformat()
            }

            for attr in user.get('Attributes', []):
                if attr['Name'] == 'email':
                    user_info['email'] = attr['Value']
                elif attr['Name'] == 'sub':
                    user_info['sub'] = attr['Value']
                elif attr['Name'] == 'email_verified':
                    user_info['email_verified'] = attr['Value'] == 'true'
                elif attr['Name'] == 'name':
                    user_info['name'] = attr['Value']

            user_info['role'] = cognito.get_user_role(user['Username'])
            users.append(user_info)

        return UserListResponse(
            users=users,
            total=len(users)
        )

    except CognitoException as e:
        raise CognitoException(f"Failed to list users: {e.response['Error']['Message']}")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Get current authenticated user information"
)
async def get_me(
    current_user: dict = Depends(get_current_active_user),
    cognito: CognitoService = Depends(get_cognito_service)
):
    """
    Get current user information
    """
    username = current_user.get('username')  # ✅ safe
    if not username:
        raise HTTPException(status_code=400, detail="Username not available")

    user_details = cognito.get_user_by_username(username)

    email = current_user.get('email') or user_details.get('email') or username

    return UserResponse(
        name=user_details.get("name", ""),
        sub=current_user.get("sub"),
        email=email,
        email_verified=current_user.get("email_verified", True),
        role=current_user.get("role", "user"),
        enabled=user_details.get("enabled", True),
        created_date=user_details.get("created_date"),
        modified_date=user_details.get("modified_date"),
        status=user_details.get("status")
    )



@router.get(
    "/{username}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user by username (Admin only)",
    description="Get detailed information about a specific user"
)
async def get_user(
    username: str,
    cognito: CognitoService = Depends(get_cognito_service),
    admin: dict = Depends(require_admin)
):
    """
    Get user by username (Admin only)
    
    - Returns detailed user information
    - Requires admin role
    """
    try:
        user = cognito.get_user_by_username(username)
    except UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except CognitoException as e:
        raise HTTPException(status_code=400, detail=e.detail)

    return UserResponse(
        name=user.get('name', ''),
        sub=user.get('sub', ''),
        email=user.get('email', ''),
        email_verified=user.get('email_verified', True),
        role=user.get('role', 'user'),
        enabled=user.get('enabled', True),
        created_date=user.get('created_date'),
        modified_date=user.get('modified_date'),
        status=user.get('status')
    )


@router.put(
    "/{username}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user (Admin only)",
    description="Update user email, role, or status"
)
async def update_user(
    username: str,
    update_data: UpdateUserRequest,
    cognito: CognitoService = Depends(get_cognito_service),
    admin: dict = Depends(require_admin)
):
    """
    Update user (Admin only)
    
    - Update email, role, or enable/disable user
    - Requires admin role
    """
    try:
        if update_data.email or update_data.role or update_data.name:
            cognito.update_user(
                username=username,
                email=update_data.email,
                role=update_data.role.value if update_data.role else None,
                name=update_data.name,
            )

        if update_data.enabled is not None:
            if update_data.enabled:
                cognito.enable_user(username)
            else:
                cognito.disable_user(username)

        return MessageResponse(message="User updated successfully")
    except UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except CognitoException as e:
        raise HTTPException(status_code=400, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.delete(
    "/{username}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete user (Admin only)",
    description="Permanently delete a user from the system"
)
async def delete_user(
    username: str,
    cognito: CognitoService = Depends(get_cognito_service),
    admin: dict = Depends(require_admin)
):
    """
    Delete user (Admin only)
    
    - Permanently removes user from Cognito
    - Cannot be undone
    - Requires admin role
    """
    try:
        cognito.delete_user(username)
    except UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except CognitoException as e:
        raise HTTPException(status_code=400, detail=e.detail)
    return MessageResponse(message="User deleted successfully")


@router.post(
    "/{username}/enable",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Enable user (Admin only)",
    description="Enable a disabled user account"
)
async def enable_user(
    username: str,
    cognito: CognitoService = Depends(get_cognito_service),
    admin: dict = Depends(require_admin)
):
    """
    Enable user (Admin only)
    
    - Enables a disabled user account
    - User can log in after enabling
    """
    try:
        cognito.enable_user(username)
    except UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except CognitoException as e:
        raise HTTPException(status_code=400, detail=e.detail)
    return MessageResponse(message="User enabled successfully")


@router.post(
    "/{username}/disable",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Disable user (Admin only)",
    description="Disable a user account"
)
async def disable_user(
    username: str,
    cognito: CognitoService = Depends(get_cognito_service),
    admin: dict = Depends(require_admin)
):
    """
    Disable user (Admin only)
    
    - Disables user account
    - User cannot log in while disabled
    """
    try:
        cognito.disable_user(username)
    except UserNotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
    except CognitoException as e:
        raise HTTPException(status_code=400, detail=e.detail)
    return MessageResponse(message="User disabled successfully")