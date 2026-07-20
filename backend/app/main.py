import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.v1.tenants import router as tenants_router
from app.api.v1.documents import router as documents_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.eval import router as eval_router
from app.api.v1.tools import router as tools_router
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings


logging.basicConfig(level=logging.INFO)
app = FastAPI(title="多租户智能客服 Agent", version="0.1.0")

# 注册租户路由，所有接口以 /api/v1 开头
app.include_router(tenants_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(eval_router, prefix="/api/v1")
app.include_router(tools_router, prefix="/api/v1")

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "env": settings.app_env,
    }



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理：捕获所有未处理的异常"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """业务异常处理：ValueError 返回 400"""
    logger.error(f"业务异常处理: {exc}", exc_info=True)
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )

#uvicorn app.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", reload=True)
