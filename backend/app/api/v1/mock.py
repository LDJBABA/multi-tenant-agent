from fastapi import APIRouter

router = APIRouter(prefix="/mock", tags=["Mock"])

@router.post("/hello")
async def mock_hello():
    return {"message": "hello world"}


@router.post("/getOrder")
async def mock_order():
    return {"orderId": "1234567890", "orderStatus": "no pay"}

@router.post("/payOrder")
async def mock_pay_order():
    return {"operation": "跳转到支付页面"}
