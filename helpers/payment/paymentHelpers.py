import razorpay
from fastapi import HTTPException
from sqlalchemy import select

from database import AsyncSession
from tables import PaymentsModel, ProductModel, Users


async def get_live_products(session: AsyncSession, product_ids: list[int]) -> dict[int, ProductModel]:
    # one IN query for the whole cart instead of a round trip per product
    result = await session.execute(
        select(ProductModel).where(
            ProductModel.id.in_(product_ids),
            ProductModel.deletedAt.is_(None)
        )
    )
    products = {product.id: product for product in result.scalars().all()}

    missing = [product_id for product_id in product_ids if product_id not in products]
    if missing:
        raise HTTPException(status_code=404, detail=f"Products not found: {missing}")
    return products


def amount_in_paise(price: float, quantity: int) -> int:
    # Razorpay works in the smallest currency unit; round once to avoid float drift
    return round(price * 100) * quantity


def create_order(client: razorpay.Client, amount_paise: int, receipt: str) -> dict:
    return client.order.create(data={
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
    })


def is_signature_valid(
    client: razorpay.Client,
    order_id: str,
    payment_id: str,
    signature: str
) -> bool:
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


async def get_user_payments(
    session: AsyncSession,
    razorpay_order_id: str,
    user: Users
) -> list[PaymentsModel]:
    result = await session.execute(
        select(PaymentsModel).where(
            PaymentsModel.razorpay_order_id == razorpay_order_id,
            PaymentsModel.paidBy == user.id
        )
    )
    payments = list(result.scalars().all())
    if not payments:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payments
