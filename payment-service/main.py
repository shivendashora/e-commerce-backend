import asyncio
from contextlib import asynccontextmanager
import os
import sys

from dotenv import load_dotenv
from bullmq import Worker

# lets this file import database.py / tables.py from the parent folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from database import get_db_session
from tables import Payments

db_session = asynccontextmanager(get_db_session)


async def handlePayment(job, job_token):
    payment_id = job.data["payment_id"]
    print(f"Processing payment {payment_id}")

    async with db_session() as session:
        payment = await session.get(Payments, payment_id)
        payment.paymentStatus = "PAID"
        await session.commit()

    return "done"


async def main():
    worker = Worker("payment-queue", handlePayment, {"connection": os.getenv("REDIS_URL")})
    print("Payment worker running")
    try:
        await asyncio.Event().wait()
    finally:
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
