import uuid
import secrets

from fastapi import APIRouter, Depends, Body, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import text
from botocore.exceptions import ClientError

from gateway.app.core.dependencies import get_current_user
from gateway.app.core.authorization import is_admin
from gateway.app.core.cognito import get_cognito_client
from gateway.app.core.config import get_settings
from gateway.app.db.session import get_engine
from gateway.app.utils.email import send_invite_email
from shared.exceptions import ForbiddenException, NotFoundException
from shared.redis import ensure_redis

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)

settings = get_settings()


# -------------------------------------------------
# COMMON
# -------------------------------------------------
def admin_only(user: dict):
    if not is_admin(user):
        raise ForbiddenException("Admin only")


_INVITE_TOKEN_TTL = 86400  # 24 hours


class CreateUserRequest(BaseModel):
    email: str
    full_name: str
    is_admin_user: bool


class ProductSuiteFields(BaseModel):
    """product/category/country: the BrandIQ/CompIQ/PredictIQ/GeoIQ landing
    page groups services by these. Must be set together or not at all — a
    service is treated as ungrouped unless all three are present. `product`
    must reference an existing products.key row (enforced by a DB foreign
    key and, for a friendlier error, by _validate_product_key below) rather
    than a hardcoded enum, so new products don't need a code change."""

    product: str | None = None
    category: str | None = None
    country: str | None = None

    @model_validator(mode="after")
    def _product_suite_all_or_nothing(self):
        values = (self.product, self.category, self.country)
        if any(values) and not all(values):
            raise ValueError("product, category, and country must be set together or not at all")
        return self


class CreateServiceRequest(ProductSuiteFields):
    name: str
    code: str
    description: str | None = None
    route: str | None = None
    icon: str | None = None


class UpdateServiceRequest(ProductSuiteFields):
    name: str
    code: str
    description: str | None = None
    route: str | None = None
    icon: str | None = None
    is_active: bool | None = None


class CreateProductRequest(BaseModel):
    key: str
    label: str
    tagline: str | None = None
    icon: str | None = None
    color: str | None = None
    sort_order: int = 0


class UpdateProductRequest(BaseModel):
    # key is immutable once created — not editable here.
    label: str | None = None
    tagline: str | None = None
    icon: str | None = None
    color: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


async def _validate_product_key(conn, product_key: str | None):
    """Friendlier 400 than the raw FK-violation 500 services_product_fkey
    would otherwise produce for an unknown product key."""
    if product_key is None:
        return
    result = await conn.execute(
        text("SELECT 1 FROM public.products WHERE key = :key"),
        {"key": product_key},
    )
    if not result.fetchone():
        raise HTTPException(status_code=400, detail=f"Unknown product key: {product_key}")


# -------------------------------------------------
# CREATE USER
# -------------------------------------------------
@router.post("/users")
async def create_user(
    body: CreateUserRequest,
    user: dict = Depends(get_current_user),
):
    admin_only(user)

    body.email = body.email.strip().lower()

    redis = await ensure_redis()
    if not redis:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

    client = get_cognito_client()
    engine = get_engine()

    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT id FROM public.users WHERE LOWER(email) = LOWER(:email)"),
            {"email": body.email},
        )
        if result.fetchone():
            raise HTTPException(status_code=409, detail="A user with this email already exists")

    # Suppress Cognito's default welcome email; set a random internal temp password
    temp_password = secrets.token_urlsafe(16) + "Aa1!"
    response = client.admin_create_user(
        UserPoolId=settings.COGNITO_USER_POOL_ID,
        Username=body.email,
        TemporaryPassword=temp_password,
        MessageAction="SUPPRESS",
        UserAttributes=[
            {"Name": "email", "Value": body.email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": body.full_name},
        ],
    )

    cognito_sub = next(
        a["Value"] for a in response["User"]["Attributes"] if a["Name"] == "sub"
    )

    client.admin_add_user_to_group(
        UserPoolId=settings.COGNITO_USER_POOL_ID,
        Username=body.email,
        GroupName="Admins" if body.is_admin_user else "Users",
    )

    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO public.users (email, cognito_sub, full_name, role, is_active)
                VALUES (:email, :sub, :name, :role, TRUE)
            """),
            {
                "email": body.email,
                "sub": cognito_sub,
                "name": body.full_name,
                "role": "ADMIN" if body.is_admin_user else "USER",
            },
        )

    token = str(uuid.uuid4())
    setup_link = f"{settings.FRONTEND_URL}/setup-password?token={token}"
    await redis.setex(f"invite:{token}", _INVITE_TOKEN_TTL, body.email)
    send_invite_email(body.email, body.full_name, setup_link)

    return {"message": "User created and invite email sent"}


# -------------------------------------------------
# LIST USERS
# -------------------------------------------------
@router.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    admin_only(user)

    async with get_engine().connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, email, full_name, role, is_active, created_at
                FROM public.users
                ORDER BY created_at DESC
            """)
        )
        rows = result.fetchall()

    return [dict(row._mapping) for row in rows]


# -------------------------------------------------
# GET USER
# -------------------------------------------------
@router.get("/users/{user_id}")
async def get_user(user_id: str, user: dict = Depends(get_current_user)):
    admin_only(user)

    async with get_engine().connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, email, full_name, role, is_active
                FROM public.users
                WHERE id = :id
            """),
            {"id": user_id},
        )
        row = result.fetchone()

    if not row:
        raise NotFoundException("User not found")

    return dict(row._mapping)


# -------------------------------------------------
# UPDATE USER
# -------------------------------------------------
@router.put("/users/{user_id}")
@router.post("/users/{user_id}")
async def update_user(
    user_id: str,
    full_name: str | None = None,
    is_active: bool | None = None,
    is_admin_user: bool | None = None,
    user: dict = Depends(get_current_user),
):
    admin_only(user)

    engine = get_engine()
    client = get_cognito_client()

    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT email FROM public.users WHERE id = :id"),
            {"id": user_id},
        )
        row = result.fetchone()

        if not row:
            raise NotFoundException("User not found")

        updates = []
        params = {"id": user_id}

        if full_name is not None:
            updates.append("full_name = :full_name")
            params["full_name"] = full_name

        if is_active is not None:
            updates.append("is_active = :is_active")
            params["is_active"] = is_active

        if is_admin_user is not None:
            updates.append("role = :role")
            params["role"] = "ADMIN" if is_admin_user else "USER"

        if updates:
            await conn.execute(
                text(f"""
                    UPDATE public.users
                    SET {", ".join(updates)}, updated_at = now()
                    WHERE id = :id
                """),
                params,
            )

    if is_admin_user is not None:
        group = "Admins" if is_admin_user else "Users"
        try:
            current_groups = client.admin_list_groups_for_user(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=row.email,
            )
            for g in current_groups.get("Groups", []):
                if g["GroupName"] != group:
                    client.admin_remove_user_from_group(
                        UserPoolId=settings.COGNITO_USER_POOL_ID,
                        Username=row.email,
                        GroupName=g["GroupName"],
                    )
            client.admin_add_user_to_group(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=row.email,
                GroupName=group,
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            if code != "UserNotFoundException":
                raise HTTPException(status_code=400, detail=f"Cognito error: {msg}")
            # user exists in DB but not in Cognito — skip group update, still return success

    return {"message": "User updated"}


# -------------------------------------------------
# DELETE USER
# -------------------------------------------------
@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(get_current_user)):
    admin_only(user)

    engine = get_engine()
    client = get_cognito_client()

    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT email FROM public.users WHERE id = :id"),
            {"id": user_id},
        )
        row = result.fetchone()

        if not row:
            raise NotFoundException("User not found")

        await conn.execute(
            text("DELETE FROM public.user_services WHERE user_id = :id"),
            {"id": user_id},
        )
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": user_id},
        )

    try:
        client.admin_delete_user(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=row.email,
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        if code != "UserNotFoundException":
            raise HTTPException(status_code=400, detail=f"Cognito error: {msg}")

    return {"message": "User deleted"}


# =================================================
# 🚀 SERVICES MANAGEMENT
# =================================================

# CREATE SERVICE
@router.post("/services")
async def create_service(
    body: CreateServiceRequest,
    user: dict = Depends(get_current_user),
):
    admin_only(user)

    async with get_engine().begin() as conn:
        await _validate_product_key(conn, body.product)

        await conn.execute(
            text("""
                INSERT INTO public.services (name, code, description, route, icon, product, category, country)
                VALUES (:name, :code, :description, :route, :icon, :product, :category, :country)
                ON CONFLICT (name) DO NOTHING
            """),
            {
                "name": body.name,
                "code": body.code,
                "description": body.description,
                "route": body.route,
                "icon": body.icon,
                "product": body.product,
                "category": body.category,
                "country": body.country,
            },
        )

    return {"message": "Service created"}


# LIST SERVICES
@router.get("/services")
async def list_services(user: dict = Depends(get_current_user)):
    admin_only(user)

    async with get_engine().connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, name, code, description, route, icon, is_active, product, category, country
                FROM public.services
            """)
        )
        rows = result.fetchall()

    return [dict(row._mapping) for row in rows]


# DELETE SERVICE
@router.delete("/services/{service_id}")
async def delete_service(service_id: str, user: dict = Depends(get_current_user)):
    admin_only(user)

    async with get_engine().begin() as conn:
        result = await conn.execute(
            text("SELECT id FROM public.services WHERE id = :id"),
            {"id": service_id},
        )
        row = result.fetchone()

        if not row:
            raise NotFoundException("Service not found")

        await conn.execute(
            text("DELETE FROM public.user_services WHERE service_id = :service_id"),
            {"service_id": service_id},
        )
        await conn.execute(
            text("DELETE FROM public.services WHERE id = :id"),
            {"id": service_id},
        )

    return {"message": "Service deleted"}


# UPDATE SERVICE
@router.patch("/services/{service_id}")
async def update_service(
    service_id: str,
    body: UpdateServiceRequest,
    user: dict = Depends(get_current_user),
):
    admin_only(user)

    fields = body.model_dump()
    fields["service_id"] = service_id

    set_clause = ", ".join(f"{k} = :{k}" for k in fields.keys() if k != "service_id")

    async with get_engine().begin() as conn:
        result = await conn.execute(
            text(f"SELECT id FROM public.services WHERE id = :service_id"),
            {"service_id": service_id},
        )
        if not result.fetchone():
            raise NotFoundException("Service not found")

        await _validate_product_key(conn, body.product)

        await conn.execute(
            text(f"UPDATE public.services SET {set_clause} WHERE id = :service_id"),
            fields,
        )

    async with get_engine().connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, name, code, description, route, icon, is_active, product, category, country
                FROM public.services WHERE id = :service_id
            """),
            {"service_id": service_id},
        )
        row = result.fetchone()

    return dict(row._mapping)


class AssignServicesRequest(BaseModel):
    service_ids: list[str]


@router.post("/users/{user_id}/services")
async def assign_services_to_user(
    user_id: str,
    body: AssignServicesRequest,
    user: dict = Depends(get_current_user),
):
    admin_only(user)

    async with get_engine().begin() as conn:
        await conn.execute(
            text("DELETE FROM public.user_services WHERE user_id = :user_id"),
            {"user_id": user_id},
        )

        for service_id in body.service_ids:
            await conn.execute(
                text("""
                    INSERT INTO public.user_services (user_id, service_id)
                    VALUES (:user_id, :service_id)
                """),
                {"user_id": user_id, "service_id": service_id},
            )

    return {"message": "Services assigned"}


# GET USER SERVICES (ADMIN VIEW)
@router.get("/users/{user_id}/services")
async def get_user_services(user_id: str, user: dict = Depends(get_current_user)):
    admin_only(user)

    async with get_engine().connect() as conn:
        result = await conn.execute(
            text("""
                SELECT s.id, s.name, s.description, s.product, s.category, s.country
                FROM public.services s
                JOIN public.user_services us ON us.service_id = s.id
                WHERE us.user_id = :user_id
            """),
            {"user_id": user_id},
        )
        rows = result.fetchall()

    return [dict(row._mapping) for row in rows]


# =================================================
# 🧩 PRODUCTS MANAGEMENT (BrandIQ / CompIQ / PredictIQ / GeoIQ, etc.)
# =================================================

# LIST PRODUCTS — any authenticated user, not admin-only: the landing page
# fetches this directly to render hub cards.
@router.get("/products")
async def list_products(user: dict = Depends(get_current_user)):
    async with get_engine().connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, key, label, tagline, icon, color, sort_order, is_active
                FROM public.products
                ORDER BY sort_order, label
            """)
        )
        rows = result.fetchall()

    return [dict(row._mapping) for row in rows]


# CREATE PRODUCT
@router.post("/products")
async def create_product(
    body: CreateProductRequest,
    user: dict = Depends(get_current_user),
):
    admin_only(user)

    async with get_engine().begin() as conn:
        existing = await conn.execute(
            text("SELECT 1 FROM public.products WHERE key = :key"),
            {"key": body.key},
        )
        if existing.fetchone():
            raise HTTPException(status_code=409, detail="A product with this key already exists")

        await conn.execute(
            text("""
                INSERT INTO public.products (key, label, tagline, icon, color, sort_order)
                VALUES (:key, :label, :tagline, :icon, :color, :sort_order)
            """),
            body.model_dump(),
        )

    return {"message": "Product created"}


# UPDATE PRODUCT — key is immutable, so it's never part of the payload here.
# No DELETE: deactivate via PATCH is_active=false instead, since dropping a
# product out from under services that still reference its key is messy.
@router.patch("/products/{product_id}")
async def update_product(
    product_id: str,
    body: UpdateProductRequest,
    user: dict = Depends(get_current_user),
):
    admin_only(user)

    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    fields["product_id"] = product_id
    set_clause = ", ".join(f"{k} = :{k}" for k in fields if k != "product_id")

    async with get_engine().begin() as conn:
        result = await conn.execute(
            text("SELECT id FROM public.products WHERE id = :product_id"),
            {"product_id": product_id},
        )
        if not result.fetchone():
            raise NotFoundException("Product not found")

        await conn.execute(
            text(f"UPDATE public.products SET {set_clause}, updated_at = now() WHERE id = :product_id"),
            fields,
        )

    async with get_engine().connect() as conn:
        result = await conn.execute(
            text("""
                SELECT id, key, label, tagline, icon, color, sort_order, is_active
                FROM public.products WHERE id = :product_id
            """),
            {"product_id": product_id},
        )
        row = result.fetchone()

    return dict(row._mapping)


# =================================================
# 👤 USER SIDE
# =================================================

# GET LOGGED-IN USER SERVICES
@router.get("/me/services")
async def get_my_services(user: dict = Depends(get_current_user)):
    async with get_engine().connect() as conn:

        # ==============================
        # STEP 1: Get DB user
        # ==============================
        user_result = await conn.execute(
            text("""
                SELECT id, role
                FROM public.users
                WHERE cognito_sub = :sub
                AND is_active = TRUE
            """),
            {"sub": user["sub"]},
        )
        user_row = user_result.fetchone()

        if not user_row:
            raise NotFoundException("User not found")

        user_id = user_row.id
        role = user_row.role

        # ==============================
        # 🔥 ADMIN → RETURN ALL SERVICES
        # ==============================
        if role == "ADMIN":
            result = await conn.execute(
                text("""
                    SELECT id, name, description, is_active, icon, route, product, category, country
                    FROM public.services
                    WHERE is_active = TRUE
                """)
            )
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

        # ==============================
        # 👤 NORMAL USER → FILTERED
        # ==============================
        result = await conn.execute(
            text("""
                SELECT s.id, s.name, s.description, s.is_active, s.icon, s.route, s.product, s.category, s.country
                FROM public.services s
                JOIN public.user_services us ON us.service_id = s.id
                WHERE us.user_id = :user_id
                AND s.is_active = TRUE
            """),
            {"user_id": user_id},
        )

        rows = result.fetchall()

    return [dict(row._mapping) for row in rows]


# =================================================
# 🔐 ACCESS CONTROL
# =================================================

def require_service(service_name: str):
    async def checker(user: dict = Depends(get_current_user)):
        async with get_engine().connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT 1
                    FROM public.user_services us
                    JOIN public.services s ON s.id = us.service_id
                    WHERE us.user_id = :user_id
                    AND s.name = :service_name
                    AND s.is_active = TRUE
                """),
                {
                    "user_id": user["id"],
                    "service_name": service_name,
                },
            )

            if not result.fetchone():
                raise ForbiddenException("Access denied")

    return checker
