from fastapi import APIRouter

router = APIRouter(prefix="/mock", tags=["Mock"])

@router.post("/hello")
async def mock_hello():
    return {"message": "hello world"}
