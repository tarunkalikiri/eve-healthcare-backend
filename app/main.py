from fastapi import FastAPI

from app.routers import auth, bookings, centres, payments, tests


app = FastAPI(
    title="EVE Healthcare Backend",
    description="Backend API for diagnostic centre bookings and payments.",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(tests.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/")
def root():
    return {
        "message": "EVE Healthcare Backend API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }