import json
import hashlib
from io import BytesIO
import base64
from pathlib import Path
from typing import Dict

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from ml.model import build_inference_transform, build_model
from ml.utils import load_class_names
from ml.visualize import compute_gradcam

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "models" / "brain_tumor_resnet18.pt"
CLASSES_PATH = ROOT_DIR / "models" / "classes.json"
METRICS_PATH = ROOT_DIR / "models" / "metrics.json"

app = FastAPI(title="NeuroScan AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def load_model() -> None:
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


@app.on_event("startup")
def startup_event() -> None:
    load_model()


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
async def predict(request: Request, file: UploadFile = File(...)) -> Dict[str, object]:
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

    result = {
        "label": predicted_label,
        "risk": float(1.0 - no_tumor_probability),
        "probabilities": probabilities,
        "model": MODEL_PATH.name,
        "glioma_margin": glioma_margin,
        "input_sha256": input_sha256,
    }

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
            b64 = base64.b64encode(buffered.getvalue()).decode('ascii')
            result['gradcam'] = b64
        except Exception:
            pass

    return result
