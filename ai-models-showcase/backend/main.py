from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import math

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock data for models
models_data = [
    {
        "id": 1,
        "name": "Qwen/Qwen3.5-2B",
        "is_new": True,
        "task": "image text to text",
        "last_updated": "2026-03-02",
        "downloads": 20,
        "category": "Multimodal"
    },
    {
        "id": 2,
        "name": "tencent/HunyuanOCR",
        "is_new": False,
        "task": "ocr",
        "last_updated": "2025-11-26",
        "downloads": 44,
        "category": "Computer Vision"
    },
    {
        "id": 3,
        "name": "Qwen/Qwen3.5-35B-A3B",
        "is_new": True,
        "task": "image text to text",
        "last_updated": "2026-02-27",
        "downloads": 29,
        "category": "Multimodal"
    },
    {
        "id": 4,
        "name": "AIWizards/LTX-2.3",
        "is_new": True,
        "task": "image to video",
        "last_updated": "2026-03-05",
        "downloads": 38,
        "category": "Computer Vision"
    },
    {
        "id": 5,
        "name": "deepseek-ai/DeepSeek-V3",
        "is_new": False,
        "task": "text generation",
        "last_updated": "2025-03-27",
        "downloads": 13780,
        "category": "Natural Language Processing"
    },
    {
        "id": 6,
        "name": "tencent/HunyuanImage-3.0",
        "is_new": False,
        "task": "text to image",
        "last_updated": "2025-10-14",
        "downloads": 3099,
        "category": "Multimodal"
    },
    # Add more models as needed
]

categories = ["Multimodal", "Computer Vision", "Natural Language Processing", "Audio Processing"]

class Model(BaseModel):
    id: int
    name: str
    is_new: bool
    task: str
    last_updated: str
    downloads: int
    category: str

@app.get("/models", response_model=List[Model])
def get_models(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = None,
    trending: bool = False
):
    filtered_models = models_data

    if category:
        filtered_models = [m for m in filtered_models if m["category"] == category]

    if trending:
        # Simulate trending by sorting by downloads descending
        filtered_models = sorted(filtered_models, key=lambda x: x["downloads"], reverse=True)

    total = len(filtered_models)
    start = (page - 1) * limit
    end = start + limit
    paginated_models = filtered_models[start:end]

    return paginated_models

@app.get("/categories")
def get_categories():
    return {"categories": categories}

@app.get("/stats")
def get_stats():
    return {"total_models": len(models_data)}