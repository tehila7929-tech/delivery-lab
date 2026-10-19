from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()

deliveries: dict[int, dict] = {}
next_id = 1

STATUSES = ["created", "in_transit", "delivered"]


def error(code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=code, content={"error": message})


# כל שגיאה (כולל 404 של נתיב לא קיים) חוזרת בפורמט {"error": "..."}
@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request: Request, exc: StarletteHTTPException):
    return error(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError):
    return error(400, "invalid request")


def valid_text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/deliveries")
async def create_delivery(request: Request):
    global next_id

    # גוף חסר / לא JSON / לא אובייקט -> 400
    try:
        body = await request.json()
    except Exception:
        return error(400, "body must be a JSON object")
    if not isinstance(body, dict):
        return error(400, "body must be a JSON object")

    recipient = body.get("recipient")
    address = body.get("address")
    if not valid_text(recipient) or not valid_text(address):
        return error(400, "recipient and address must be non-empty strings")

    delivery = {
        "id": next_id,
        "recipient": recipient,
        "address": address,
        "status": "created",
    }
    deliveries[next_id] = delivery
    next_id += 1
    return JSONResponse(status_code=201, content=delivery)


@app.get("/deliveries")
def list_deliveries(status: Optional[str] = None):
    if status is not None and status not in STATUSES:
        return error(400, "unknown status")
    items = list(deliveries.values())
    if status is not None:
        items = [d for d in items if d["status"] == status]
    return items


@app.get("/deliveries/{delivery_id}")
def get_delivery(delivery_id: int):
    delivery = deliveries.get(delivery_id)
    if delivery is None:
        return error(404, "delivery not found")
    return delivery


@app.patch("/deliveries/{delivery_id}/status")
async def update_status(delivery_id: int, request: Request):
    delivery = deliveries.get(delivery_id)
    if delivery is None:
        return error(404, "delivery not found")

    try:
        body = await request.json()
    except Exception:
        return error(400, "body must be a JSON object")
    if not isinstance(body, dict):
        return error(400, "body must be a JSON object")

    new_status = body.get("status")
    if not isinstance(new_status, str) or new_status not in STATUSES:
        return error(400, "invalid status")

    current_index = STATUSES.index(delivery["status"])
    new_index = STATUSES.index(new_status)

    # רק צעד אחד קדימה; דילוג, חזרה או אותו סטטוס -> 409
    if new_index != current_index + 1:
        return error(409, "invalid status transition")

    delivery["status"] = new_status
    return delivery


@app.delete("/deliveries/{delivery_id}")
def delete_delivery(delivery_id: int):
    delivery = deliveries.get(delivery_id)
    if delivery is None:
        return error(404, "delivery not found")
    if delivery["status"] != "created":
        return error(409, "only created deliveries can be deleted")
    del deliveries[delivery_id]
    return Response(status_code=204)