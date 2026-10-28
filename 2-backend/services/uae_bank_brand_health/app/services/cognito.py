import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, List
from services.uae_bank_brand_health.app.core.config import get_settings
from services.uae_bank_brand_health.app.core.security import calculate_secret_hash
from services.uae_bank_brand_health.app.utils.exceptions import (
    CognitoException,
    AuthenticationException,
    UserNotFoundException,
    ForbiddenException
)

settings = get_settings()

class CognitoService:
    def __init__(self):
        self.client = boto3.client(
            'cognito-idp',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        self.user_pool_id = settings.COGNITO_USER_POOL_ID
        self.client_id = settings.COGNITO_CLIENT_ID

    # -----------------------------
    # Authentication
    # -----------------------------
    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        try:
            auth_params = {'USERNAME': email, 'PASSWORD': password}
            secret_hash = calculate_secret_hash(email)
            if secret_hash:
                auth_params['SECRET_HASH'] = secret_hash

            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters=auth_params
            )
            return response
        except ClientError as e:
            code = e.response['Error']['Code']
            if code == 'NotAuthorizedException':
                raise AuthenticationException("Incorrect email or password")
            elif code == 'UserNotFoundException':
                raise UserNotFoundException("User not found")
            elif code == 'UserNotConfirmedException':
                raise AuthenticationException("User account not confirmed")
            else:
                raise AuthenticationException(f"Authentication failed: {e.response['Error']['Message']}")

    # -----------------------------
    # User Management
    # -----------------------------
    def create_user(self, email: str, temporary_password: str, role: str = "user", name: str = "") -> Dict[str, Any]:
        try:
            response = self.client.admin_create_user(
                UserPoolId=self.user_pool_id,
                Username=email,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'email_verified', 'Value': 'true'},
                    {'Name': 'name', 'Value': name}
                ],
                TemporaryPassword=temporary_password,
                MessageAction='SUPPRESS',
                DesiredDeliveryMediums=['EMAIL']
            )

            group_name = settings.ADMIN_GROUP_NAME if role == "admin" else settings.USER_GROUP_NAME
            try:
                self.client.admin_add_user_to_group(UserPoolId=self.user_pool_id, Username=email, GroupName=group_name)
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    self._create_group(group_name)
                    self.client.admin_add_user_to_group(UserPoolId=self.user_pool_id, Username=email, GroupName=group_name)

            return response
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            if error_code == 'UsernameExistsException':
                raise CognitoException("User already exists")
            elif error_code == 'InvalidPasswordException':
                raise CognitoException(f"Invalid password: {error_message}")
            else:
                raise CognitoException(f"Failed to create user: {error_message}")

    def _create_group(self, group_name: str):
        try:
            self.client.create_group(GroupName=group_name, UserPoolId=self.user_pool_id, Description=f"{group_name} group")
        except ClientError:
            pass

    def list_users(self, limit: int = 60) -> List[Dict[str, Any]]:
        try:
            response = self.client.list_users(UserPoolId=self.user_pool_id, Limit=limit)
            users = []
            for user in response.get('Users', []):
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

                user_info['role'] = self.get_user_role(user['Username'])
                users.append(user_info)

            return users
        except ClientError as e:
            raise CognitoException(f"Failed to list users: {e.response['Error']['Message']}")
    

    def list_users_by_groups(self) -> List[Dict[str, Any]]:
        users = {}
        
        for group in [settings.ADMIN_GROUP_NAME, settings.USER_GROUP_NAME]:
            try:
                response = self.client.list_users_in_group(
                    UserPoolId=self.user_pool_id,
                    GroupName=group
                )
            except ClientError as e:
                continue  # if group doesn't exist, skip

            for user in response.get("Users", []):
                users[user["Username"]] = user  # merge, avoid duplicates

        return list(users.values())


    def get_user_by_username(self, username: str) -> Dict[str, Any]:
        try:
            response = self.client.admin_get_user(UserPoolId=self.user_pool_id, Username=username)
            user_info = {
                'username': response['Username'],
                'status': response['UserStatus'],
                'enabled': response['Enabled'],
                'created_date': response['UserCreateDate'].isoformat(),
                'modified_date': response['UserLastModifiedDate'].isoformat()
            }

            for attr in response.get('UserAttributes', []):
                if attr['Name'] == 'email':
                    user_info['email'] = attr['Value']
                elif attr['Name'] == 'sub':
                    user_info['sub'] = attr['Value']
                elif attr['Name'] == 'email_verified':
                    user_info['email_verified'] = attr['Value'] == 'true'
                elif attr['Name'] == 'name':
                    user_info['name'] = attr['Value']

            user_info['role'] = self.get_user_role(username)
            return user_info
        except ClientError as e:
            code = e.response['Error']['Code']
            if code == 'UserNotFoundException':
                raise UserNotFoundException("User not found")
            raise CognitoException(f"Failed to get user: {e.response['Error']['Message']}")

    def update_user(self, username: str, email: str = None, role: str = None, name: str = None) -> Dict[str, Any]:
        try:
            attributes = []
            if email:
                attributes.append({'Name': 'email', 'Value': email})
                attributes.append({'Name': 'email_verified', 'Value': 'true'})
            if name:
                attributes.append({'Name': 'name', 'Value': name})

            if attributes:
                self.client.admin_update_user_attributes(UserPoolId=self.user_pool_id, Username=username, UserAttributes=attributes)

            if role:
                current_groups = self.client.admin_list_groups_for_user(Username=username, UserPoolId=self.user_pool_id)
                for group in current_groups.get('Groups', []):
                    self.client.admin_remove_user_from_group(UserPoolId=self.user_pool_id, Username=username, GroupName=group['GroupName'])

                group_name = settings.ADMIN_GROUP_NAME if role == "admin" else settings.USER_GROUP_NAME
                try:
                    self.client.admin_add_user_to_group(UserPoolId=self.user_pool_id, Username=username, GroupName=group_name)
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        self._create_group(group_name)
                        self.client.admin_add_user_to_group(UserPoolId=self.user_pool_id, Username=username, GroupName=group_name)

            return {"message": "User updated successfully"}
        except ClientError as e:
            raise CognitoException(f"Failed to update user: {e.response['Error']['Message']}")

    def enable_user(self, username: str):
        try:
            self.client.admin_enable_user(UserPoolId=self.user_pool_id, Username=username)
        except ClientError as e:
            raise CognitoException(f"Failed to enable user: {e.response['Error']['Message']}")

    def disable_user(self, username: str):
        try:
            self.client.admin_disable_user(UserPoolId=self.user_pool_id, Username=username)
        except ClientError as e:
            raise CognitoException(f"Failed to disable user: {e.response['Error']['Message']}")

    def delete_user(self, username: str):
        try:
            self.client.admin_delete_user(UserPoolId=self.user_pool_id, Username=username)
        except ClientError as e:
            if e.response['Error']['Code'] == 'UserNotFoundException':
                raise UserNotFoundException("User not found")
            raise CognitoException(f"Failed to delete user: {e.response['Error']['Message']}")

    # -----------------------------
    # Helper: get role from group
    # -----------------------------
    def get_user_role(self, username: str) -> str:
        try:
            response = self.client.admin_list_groups_for_user(Username=username, UserPoolId=self.user_pool_id)
            groups = [g['GroupName'] for g in response.get('Groups', [])]
            if settings.ADMIN_GROUP_NAME in groups:
                return "admin"
            return "user"
        except ClientError:
            return "user"

    # -----------------------------
    # Password challenge
    # -----------------------------
    def respond_to_new_password_challenge(self, email: str, session: str, new_password: str) -> Dict[str, Any]:
        try:
            challenge_responses = {'USERNAME': email, 'NEW_PASSWORD': new_password}
            secret_hash = calculate_secret_hash(email)
            if secret_hash:
                challenge_responses['SECRET_HASH'] = secret_hash

            response = self.client.respond_to_auth_challenge(
                ClientId=self.client_id,
                ChallengeName='NEW_PASSWORD_REQUIRED',
                Session=session,
                ChallengeResponses=challenge_responses
            )
            return response
        except ClientError as e:
            raise CognitoException(f"Failed to set new password: {e.response['Error']['Message']}")
