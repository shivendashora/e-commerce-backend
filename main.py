from contextlib import asynccontextmanager
import time

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import razorpay
from sqlalchemy import select
import uvicorn
from dotenv import load_dotenv
import os

import logging
from database import AsyncSession,engine,get_db_session,init_db
from model import PaymentRequest, VerifyPaymentRequest
from tables import PaymentsModel, ProductModel, Users
from auth import router as auth_router
from helpers.auth.authHelpers import get_current_user
from helpers.files.storeFiles import storeFiles, deleteStoredFile
from redis_fastapi import FastAPIRedis, cache, cache_evict
from helpers.products.productHelpers import (
    apply_product_updates,
    filteredSearch,
    get_owned_product,
    product_response,
    soft_delete_product,
)
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from helpers.payment.paymentHelpers import (
    amount_in_paise,
    create_order,
    get_live_products,
    get_user_payments,
    is_signature_valid,
)

class CustomRateLimiter(BaseHTTPMiddleware):

    def __init__(self, app, request_limit: int = 60, limit_window: int = 60):
        super().__init__(app)
        self.request_limit = request_limit
        self.limit_window = limit_window
        self.counter = 0
        self.window_start = time.monotonic()

    async def dispatch(self, request: Request, call_next):
        now = time.monotonic()

        if now - self.window_start >= self.limit_window:
            self.window_start = now        
            self.counter = 0

        if self.counter >= self.request_limit:
            retry_after = int(self.limit_window - (now - self.window_start)) + 1
            return JSONResponse(
                status_code=429,
                content={"message": "Server busy, try again later"},
                headers={"Retry-After": str(retry_after)},
            )

        self.counter += 1
        return await call_next(request)



@asynccontextmanager
async def lifecycle(app: FastAPI):

    await init_db()
    yield

    await engine.dispose()


app = FastAPI(
    lifespan = lifecycle,
    swagger_ui_parameters = {"persistAuthorization": True},
)
app.include_router(auth_router)
app.add_middleware(CustomRateLimiter)
FastAPIRedis(app).lifespan().caching()
load_dotenv()

port = int(os.getenv("port"))
upload_path = os.getenv("upload_dir")
TEST_KEY = os.getenv("TEST_KEY")
TEST_KEY_SECRET = os.getenv("TEST_KEY_SECRET")
PRODUCTS_CACHE = "products"


app.mount("/static", StaticFiles(directory=upload_path), name="static")

if not TEST_KEY or not TEST_KEY_SECRET:
    raise RuntimeError("Razorpay API keys are missing")



client = razorpay.Client(
    auth=(TEST_KEY, TEST_KEY_SECRET)
)





logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.perf_counter()

    logger.info(
        "Request received | Method: %s | URL: %s",
        request.method,
        request.url
    )

    try:
        response = await call_next(request)

        process_time = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Response sent | Method: %s | URL: %s | Status: %s | Time: %.2f ms",
            request.method,
            request.url,
            response.status_code,
            process_time
        )

        response.headers["X-Process-Time"] = f"{process_time:.2f} ms"

        return response

    except Exception:
        process_time = (time.perf_counter() - start_time) * 1000

        logger.exception(
            "Request failed | Method: %s | URL: %s | Time: %.2f ms",
            request.method,
            request.url,
            process_time
        )

        raise

@app.get('/')
def index():
    return{
        "message":f'Server running at {port}'
    }



@app.post("/list-product",
    dependencies=[Depends(cache_evict(eviction_group=PRODUCTS_CACHE))])
async def list_product(
    name: str = Form(...),
    price: float = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: Users = Depends(get_current_user),
):
    if not name:
        return {"message": "Product details not present"}

    stored_name = await storeFiles(upload_path,file)

    structured_product = ProductModel(
        name=name,
        price=price,
        description=description,
        addedBy=current_user.id,
        thumbnail_path = stored_name
    )

    session.add(structured_product)
    await session.commit()
    await session.refresh(structured_product)

    return {
        "message": "Product listed successfully",
        "product_id": structured_product.id,
    }


@app.put("/update-product",
    dependencies=[Depends(cache_evict(eviction_group=PRODUCTS_CACHE))])
async def updateProduct(
    request: Request,
    productId: int,
    name: str | None = Form(None),
    price: float | None = Form(None),
    description: str | None = Form(None),
    ratings: float | None = Form(None),
    file: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_db_session),
    current_user: Users = Depends(get_current_user)
):
    productDbData = await get_owned_product(session, productId, current_user)

    apply_product_updates(productDbData, {
        "name": name,
        "price": price,
        "description": description,
        "ratings": ratings,
    })

    old_thumbnail = None
    if file is not None and file.filename:
        old_thumbnail = productDbData.thumbnail_path
        productDbData.thumbnail_path = await storeFiles(upload_path, file)

    await session.commit()
    await session.refresh(productDbData)

    if old_thumbnail:
        deleteStoredFile(upload_path, old_thumbnail)

    return {
        "message": f"Updated product details for {productId}",
        "data": product_response(request, productDbData)
    }


@app.get("/fetchAllProducts",
    dependencies=[Depends(cache(ttl=60, eviction_group=PRODUCTS_CACHE))])
async def fetchProducts(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    offset : int = 0,
    search : str | None = None,
    limit:int = 10
):
    query = select(ProductModel).where(ProductModel.deletedAt.is_(None))

    term = filteredSearch(search) if search else ""
    if term:
        query = query.where(ProductModel.name.ilike(f"%{term}%"))

    query = query.order_by(ProductModel.id).offset(offset).limit(limit)

    result = await session.execute(query)
    products = result.scalars().all()

    return {
        "message": "Fetched products successfully",
        "data": [product_response(request, product) for product in products]
    }


@app.delete('/delete-product/{product_id}',
    dependencies=[Depends(cache_evict(eviction_group=PRODUCTS_CACHE))])
async def delete_product(
    product_id : int,
    session: AsyncSession = Depends(get_db_session),
    current_user: Users = Depends(get_current_user)
):
    product = await get_owned_product(session, product_id, current_user)

    soft_delete_product(product)

    await session.commit()

    return{
        "message":"Product deleted successfully",
        "product_id":product_id
    }



@app.post('/trigger-payment')
async def triggerPayment(
    payment : PaymentRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: Users = Depends(get_current_user)
):
    # the same product listed twice in a cart is merged into one line
    quantities: dict[int, int] = {}
    for item in payment.PaymentRequest:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity

    products = await get_live_products(session, list(quantities))

    line_costs: dict[int, int] = {}
    for product_id, quantity in quantities.items():
        product = products[product_id]
        if product.addedBy == current_user.id:
            raise HTTPException(
                status_code=400,
                detail=f"You cannot buy your own product: {product_id}"
            )
        line_costs[product_id] = amount_in_paise(product.price, quantity)

    # one razorpay order for the whole cart so the user pays once
    amount = sum(line_costs.values())
    receipt = f"u{current_user.id}-n{len(quantities)}-{int(time.time())}"

    try:
        # razorpay's client is blocking; run it off the event loop but still wait for it
        order = await run_in_threadpool(create_order, client, amount, receipt)
    except Exception:
        logger.exception("Razorpay order creation failed | products: %s", list(quantities))
        raise HTTPException(status_code=502, detail="Could not create payment order")

    new_payments = []
    for product_id, quantity in quantities.items():
        new_payments.append(PaymentsModel(
            product_id=product_id,
            quantity=quantity,
            cost=line_costs[product_id],
            paymentStatus="created",
            paidTo=products[product_id].addedBy,
            paidBy=current_user.id,
            razorpay_order_id=order["id"],
        ))
    session.add_all(new_payments)
    await session.commit()

    return {
        "message": "Order created",
        "payment_ids": [new_payment.id for new_payment in new_payments],
        "order_id": order["id"],
        "amount": amount,
        "currency": order["currency"],
        "key": TEST_KEY,
    }


@app.post('/verify-payment')
async def verifyPayment(
    body : VerifyPaymentRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: Users = Depends(get_current_user)
):
    payments = await get_user_payments(session, body.razorpay_order_id, current_user)
    payment_ids = [payment.id for payment in payments]

    # repeat calls (e.g. client retries) return the stored result instead of re-verifying
    if all(payment.paymentStatus == "paid" for payment in payments):
        return {"message": "Payment already verified", "payment_ids": payment_ids}

    valid = is_signature_valid(
        client,
        body.razorpay_order_id,
        body.razorpay_payment_id,
        body.razorpay_signature
    )

    if not valid:
        for payment in payments:
            payment.paymentStatus = "failed"
        await session.commit()
        raise HTTPException(status_code=400, detail="Payment verification failed")

    for payment in payments:
        payment.paymentStatus = "paid"
        payment.razorpay_payment_id = body.razorpay_payment_id
    await session.commit()

    return {
        "message": "Payment successful",
        "payment_ids": payment_ids,
        "status": "paid",
    }



if __name__== "__main__":
    uvicorn.run(app = app,port = port)