from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
import uvicorn
from dotenv import load_dotenv
import os
from database import AsyncSession,engine,get_db_session,init_db
from tables import ProductModel, Users
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



@asynccontextmanager
async def lifecycle(app: FastAPI):

    await init_db()
    yield

    await engine.dispose()


app = FastAPI(
    lifespan = lifecycle,
    swagger_ui_parameters = {"persistAuthorization": True}
)
app.include_router(auth_router)
FastAPIRedis(app).lifespan().caching()
load_dotenv()

port = int(os.getenv("port"))
upload_path = os.getenv("upload_dir")
PRODUCTS_CACHE = "products"


app.mount("/static", StaticFiles(directory=upload_path), name="static")


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
def triggerPayment():
    return{
        "message":"Payment Successfull"
    }



if __name__== "__main__":
    uvicorn.run(app = app,port = port)