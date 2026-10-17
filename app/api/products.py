
from decimal import Decimal
from app.api.auth import get_current_user
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from uuid import UUID

from app.db.config import supabase, admin_supabase
from app.core.permissions import require_admin

router = APIRouter(tags=["Products"])


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    image_url: str | None = None


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    image_url: str | None = None
    is_active: bool | None = None


class StockAddition(BaseModel):
    quantity: int = Field(gt=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=500)


def db_error(exc: Exception):
    # Log full details server-side in a production application.
    return HTTPException(
        status_code=400,
        detail="Database operation failed. Check the submitted data.",
    )


# CUSTOMER: list active products
@router.get("/api/products")
def list_products(
    search: str | None = Query(default=None, max_length=100),
):
    query = (
        supabase.table("products")
        .select(
            "id,sku,name,description,price,stock_quantity,image_url"
        )
        .eq("is_active", True)
        .order("name")
    )

    if search and search.strip():
        term = search.strip().replace("%", "").replace(",", "")
        query = query.ilike("name", f"%{term}%")

    return query.execute().data


# CUSTOMER: get one active product
@router.get("/api/products/{product_id}")
def get_product(product_id: UUID):
    result = (
        supabase.table("products")
        .select(
            "id,sku,name,description,price,stock_quantity,image_url"
        )
        .eq("id", str(product_id))
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Product not found")

    return result.data[0]


# ADMIN: add a product with zero initial stock
@router.post("/api/admin/products", status_code=201)
def create_product(
    payload: ProductCreate,
    admin=Depends(require_admin),
):
    data = payload.model_dump(mode="json")
    data["sku"] = data["sku"].strip()
    data["name"] = data["name"].strip()

    if not data["sku"] or not data["name"]:
        raise HTTPException(
            status_code=422,
            detail="SKU and name cannot be blank",
        )

    try:
        result = (
            admin_supabase.table("products")
            .insert(data)
            .execute()
        )
        return result.data[0]
    except Exception as exc:
        print(f"exception : {exc}")
        raise db_error(exc) from exc


# ADMIN: update product details
@router.patch("/api/admin/products/{product_id}")
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    admin=Depends(require_admin),
):
    data = payload.model_dump(
        mode="json",
        exclude_unset=True,
    )

    if not data:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update",
        )

    for field in ("sku", "name"):
        if field in data:
            data[field] = data[field].strip()
            if not data[field]:
                raise HTTPException(
                    status_code=422,
                    detail=f"{field} cannot be blank",
                )

    data["updated_at"] = "now()"

    # Use a database timestamp rather than a literal SQL expression.
    data.pop("updated_at")

    try:
        result = (
            admin_supabase.table("products")
            .update(data)
            .eq("id", str(product_id))
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Product not found",
            )

        return result.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        print(f"exception : {exc}")
        raise db_error(exc) from exc


# ADMIN: add stock and record its movement atomically
@router.post("/api/admin/products/{product_id}/stock")
def add_stock(
    product_id: UUID,
    payload: StockAddition,
    admin=Depends(require_admin),
):
    try:
        result = admin_supabase.rpc(
            "admin_add_stock",
            {
                "p_product_id": str(product_id),
                "p_quantity": payload.quantity,
                "p_performed_by": str(admin.id),
                "p_note": payload.note,
            },
        ).execute()

        return {
            "message": "Stock added successfully",
            **result.data[0],
        }
    except Exception as exc:
        print(f"exception : {exc}")
        raise db_error(exc) from exc
