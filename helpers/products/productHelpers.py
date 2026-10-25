from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select

from database import AsyncSession
from tables import ProductModel, Users
from sqlalchemy.orm import joinedload


def thumbnail_url(request: Request, thumbnail_path: str | None) -> str | None:
    # DB keeps only the stored filename; turn it into a URL served by the /static mount
    if not thumbnail_path:
        return None
    if thumbnail_path.startswith(("http://", "https://")):
        return thumbnail_path
    filename = thumbnail_path.removeprefix("/static/")
    return str(request.url_for("static", path=filename))


def product_response(request: Request, product: ProductModel) -> dict:
    data = {column.name: getattr(product, column.name) for column in ProductModel.__table__.columns}
    data["thumbnail_path"] = thumbnail_url(request, product.thumbnail_path)
    return data


async def get_owned_product(
    session: AsyncSession,
    product_id: int,
    user: Users
) -> ProductModel:

    query = (
        select(ProductModel)
        .options(joinedload(ProductModel.category))
        .where(
            ProductModel.id == product_id,
            ProductModel.deletedAt.is_(None)
        )
    )

    result = await session.execute(query)
    product = result.scalars().one_or_none()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    if product.addedBy != user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only modify your own products"
        )

    return product

def apply_product_updates(product: ProductModel, updated_fields: dict) -> None:
    # only fields that were actually sent get updated
    for field, new_value in updated_fields.items():
        if new_value is not None and getattr(product, field) != new_value:
            setattr(product, field, new_value)


def soft_delete_product(product: ProductModel) -> None:
    # keep the row, hide it from listings
    product.deletedAt = datetime.now(timezone.utc)

def filteredSearch(search: str) -> str:
    search = search.strip()
    return "".join(ch for ch in search if ch.isalnum() or ch == " ")

