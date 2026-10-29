from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Product(BaseModel):

    name:str = Field(max_length=15,min_length=1)
    description:str = Field(max_length=250,min_length=10)
    price:float = Field()
    ratings:float = Field()
    thumbnail_path:str = Field()


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_within_bcrypt_limit(cls, value: str) -> str:
        # bcrypt only uses the first 72 bytes of a password
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PaymentRequestStructure(BaseModel):
    # cost and status are decided by the server, never trusted from the client
    model_config = ConfigDict(populate_by_name=True)

    product_id:int = Field(gt=0, alias="productId")
    quantity : int = Field(gt=0, le=100)


class PaymentRequest(BaseModel):
    PaymentRequest : list[PaymentRequestStructure] = Field(min_length=1, max_length=50)


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id:str = Field(min_length=1)
    razorpay_payment_id:str = Field(min_length=1)
    razorpay_signature:str = Field(min_length=1)

