from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.products import router as products_router
from app.api.orders import router as orders_router
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

origins = [
    "http://localhost:3000",      # Common React frontend port
    "https://yourdomain.com",     # Production domain
]

# Add the CORS middleware to your FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Allows specific origins
    allow_credentials=True,           # Allows cookies and credentials
    allow_methods=["*"],              # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],              # Allows all HTTP headers
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(products_router)
app.include_router(orders_router)

@app.get("/")
def read_root():
    return {"hello" : "world"}


@app.get("/health")
def read_root():
    return {"healthCheck" : "good"}

@app.get("/v1/models")
def read_root():
    return {"models": ["chat", "auth", "documents", "products", "orders"]}