import json
import hashlib
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
import base64
from pathlib import Path
from typing import Dict

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image

from ml.model import build_inference_transform, build_model
from ml.utils import load_class_names
from ml.visualize import compute_gradcam

from backend.config import settings
from backend.database import engine, Base, get_db
from backend.auth.dependencies import get_optional_user
from backend.auth.router import router as auth_router
from backend.routers.history import router as history_router
from backend.routers.admin import router as admin_router
from backend.routers.images import router as images_router
from backend.models.scan_result import ScanResult, ScanImage
from backend.models.audit_log import AuditLog
from backend.models.user import User


import backend.models

from sqlalchemy.ext.asyncio import AsyncSession

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "models" / "brain_tumor_resnet18.pt"
CLASSES_PATH = ROOT_DIR / "models" / "classes.json"
METRICS_PATH = ROOT_DIR / "models" / "metrics.json"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
transform = build_inference_transform()
model = None
class_names = []
glioma_margin = 0.0
model_info = {
    "name": None,
    "architecture": None,
    "image_size": None,
}


def load_ml_model() -> None:
    global model, class_names, transform, glioma_margin

    if not MODEL_PATH.exists() or not CLASSES_PATH.exists():
        model = None
        class_names = []
        glioma_margin = 0.0
        model_info["name"] = None
        model_info["architecture"] = None
        model_info["image_size"] = None
        return

    state = torch.load(MODEL_PATH, map_location=device, weights_only=True)
    class_names = state.get("classes") or load_class_names(CLASSES_PATH)
    architecture = state.get("architecture", "simple_cnn")
    image_size = state.get("image_size", 224)
    transform = build_inference_transform(image_size)
    loaded_model = build_model(
        num_classes=len(class_names),
        architecture=architecture,
        pretrained=False,
    )
    loaded_model.load_state_dict(state["model_state_dict"])
    loaded_model.to(device)
    loaded_model.eval()
    model = loaded_model

    model_info["name"] = MODEL_PATH.name
    model_info["architecture"] = architecture
    model_info["image_size"] = image_size

    glioma_margin = 0.0
    if METRICS_PATH.exists():
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        glioma_margin = float(metrics.get("best_glioma_margin", 0.0))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    load_ml_model()
    yield


app = FastAPI(title="NeuroScan AI API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(history_router)
app.include_router(admin_router)
app.include_router(images_router)





def predict_label_with_glioma_margin(probabilities: Dict[str, float]) -> str:
    predicted_label = max(probabilities, key=probabilities.get)
    glioma_probability = probabilities.get("glioma")
    if glioma_probability is None or glioma_margin <= 0:
        return predicted_label

    top_probability = probabilities[predicted_label]
    if glioma_probability >= top_probability - glioma_margin:
        return "glioma"
    return predicted_label


@app.post("/predict")
async def predict(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> Dict[str, object]:
    if model is None:
        raise HTTPException(
            status_code=503,
            detail=f"Model is not trained yet. Run ml/train.py and save {MODEL_PATH.name}.",
        )

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload an image file.")

    file_bytes = await file.read()
    input_sha256 = hashlib.sha256(file_bytes).hexdigest()
    image = Image.open(BytesIO(file_bytes)).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(tensor)
        probabilities_tensor = torch.softmax(logits, dim=1).squeeze(0).cpu()

    probabilities = {
        class_name: float(probabilities_tensor[index])
        for index, class_name in enumerate(class_names)
    }
    predicted_label = predict_label_with_glioma_margin(probabilities)
    no_tumor_probability = max(
        probabilities.get("no_tumor", 0.0),
        probabilities.get("notumor", 0.0),
        probabilities.get("No tumor", 0.0),
    )

    risk = float(1.0 - no_tumor_probability)


    gradcam_b64 = None
    gradcam_requested = False
    try:
        if request.query_params.get("gradcam", "0").lower() in ("1", "true", "yes"):
            gradcam_requested = True
    except Exception:
        gradcam_requested = False

    if gradcam_requested:
        try:
            heatmap, _ = compute_gradcam(model, tensor, target_layer_name="layer4", device=device)
            from PIL import Image as PILImage
            h = (heatmap * 255).astype('uint8')
            im = PILImage.fromarray(h)
            buffered = BytesIO()
            im.save(buffered, format="PNG")
            gradcam_b64 = base64.b64encode(buffered.getvalue()).decode('ascii')
        except Exception:
            pass


    scan_result_id = uuid.uuid4()


    upload_dir = settings.upload_path
    original_filename = f"{scan_result_id}_original.png"
    original_path = upload_dir / original_filename
    image.save(str(original_path), format="PNG")


    image_features = None
    try:
        features_param = request.query_params.get("features")
        if features_param:
            image_features = json.loads(features_param)
    except Exception:
        pass

    scan_result = ScanResult(
        id=scan_result_id,
        user_id=current_user.id if current_user else None,
        session_id=request.query_params.get("session_id"),
        file_name=file.filename or "unknown",
        file_sha256=input_sha256,
        predicted_label=predicted_label,
        risk_score=risk,
        probabilities=probabilities,
        image_features=image_features,
        model_name=MODEL_PATH.name,
        model_architecture=model_info.get("architecture"),
        glioma_margin=glioma_margin,
        gradcam_generated=gradcam_b64 is not None,
        notes=None,
    )
    db.add(scan_result)


    original_image = ScanImage(
        scan_result_id=scan_result_id,
        image_type="original",
        storage_path=original_filename,
        file_size_bytes=len(file_bytes),
        mime_type=file.content_type,
    )
    db.add(original_image)


    if gradcam_b64:
        gradcam_filename = f"{scan_result_id}_gradcam.png"
        gradcam_path = upload_dir / gradcam_filename
        gradcam_bytes = base64.b64decode(gradcam_b64)
        gradcam_path.write_bytes(gradcam_bytes)
        gradcam_image = ScanImage(
            scan_result_id=scan_result_id,
            image_type="gradcam",
            storage_path=gradcam_filename,
            file_size_bytes=len(gradcam_bytes),
            mime_type="image/png",
        )
        db.add(gradcam_image)


    db.add(AuditLog(
        user_id=current_user.id if current_user else None,
        action="predict",
        ip_address=request.client.host if request.client else None,
        details={
            "file_name": file.filename,
            "predicted_label": predicted_label,
            "risk_score": risk,
            "scan_result_id": str(scan_result_id),
        },
    ))

    result = {
        "id": str(scan_result_id),
        "label": predicted_label,
        "risk": risk,
        "probabilities": probabilities,
        "model": MODEL_PATH.name,
        "glioma_margin": glioma_margin,
        "input_sha256": input_sha256,
    }

    if gradcam_b64:
        result['gradcam'] = gradcam_b64

    return result



app.mount("/src", StaticFiles(directory=ROOT_DIR / "src"), name="src")


@app.get("/")
async def read_index():
    return FileResponse(ROOT_DIR / "index.html")


@app.get("/admin.html")
@app.get("/admin")
async def read_admin():
    return FileResponse(ROOT_DIR / "admin.html")
