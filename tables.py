from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Float, Boolean, func, text
from database import base



class BaseColumn:

    __tablename__  = "basecolumn"


    createdAt = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updatedAt = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True
    )

    deletedAt = Column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )   

class ProductModel(BaseColumn,base):
    __tablename__ = "products"
    __table_args__ = (
        # trigram GIN index so `name ILIKE '%term%'` searches can use an index;
        # partial on live rows because every listing filters deletedAt IS NULL
        Index(
            "idx_products_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
            postgresql_where=text('"deletedAt" IS NULL'),
        ),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    thumbnail_path = Column(String, nullable=True)
    ratings = Column(Float, nullable=True)
    addedBy = Column(Integer,ForeignKey("users.id"),nullable=False)

class Users(BaseColumn,base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class Payments(BaseColumn,base):
    __tablename__ = "payments"

    id = Column(Integer,primary_key=True)
    product_id = Column(Integer,ForeignKey("products.id"))
    quantity = Column(Integer)
    cost = Column(Integer)
    paymentStatus = Column(Integer)