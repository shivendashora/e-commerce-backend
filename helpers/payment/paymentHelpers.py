import razorpay
from fastapi import HTTPException
from sqlalchemy import select

from database import AsyncSession
from tables import PaymentsModel, ProductModel, Users


async def get_live_product(session: AsyncSession, product_id: int) -> ProductModel:
    result = await session.execute(
        select(ProductModel).where(
            ProductModel.id == product_id,
            ProductModel.deletedAt.is_(None)
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


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


async def get_user_payment(
    session: AsyncSession,
    razorpay_order_id: str,
    user: Users
) -> PaymentsModel:
    result = await session.execute(
        select(PaymentsModel).where(
            PaymentsModel.razorpay_order_id == razorpay_order_id,
            PaymentsModel.paidBy == user.id
        )
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
