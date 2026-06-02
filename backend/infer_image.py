from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import torch
from PIL import Image
import hashlib
import numpy as np

from ml.model import build_inference_transform, build_model
from ml.utils import load_class_names
from ml.visualize import compute_gradcam, visualize_gradcam_on_image


DEFAULT_MODEL_PATH = Path("models") / "brain_tumor_resnet18.pt"
DEFAULT_FALLBACK_MODEL_PATH = Path("models") / "brain_tumor_cnn.pt"
DEFAULT_CLASSES_PATH = Path("models") / "classes.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a single MRI image through the NeuroScan model for inference."
    )
    parser.add_argument("image", type=Path, help="Path to the input MRI image file.")
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Path to the model checkpoint file. Defaults to models/brain_tumor_resnet18.pt or models/brain_tumor_cnn.pt.",
    )
    parser.add_argument(
        "--classes",
        type=Path,
        default=DEFAULT_CLASSES_PATH,
        help="Path to the classes JSON file. Defaults to models/classes.json.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Compute device for inference: cuda or cpu.",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=4,
        help="Show the top K predicted classes.",
    )
    parser.add_argument("--gradcam", action="store_true", help="Compute Grad-CAM overlay and save PNG next to the image.")
    parser.add_argument("--target-layer", type=str, default=None, help="Target layer name for Grad-CAM (e.g. 'layer4'). If omitted, inferred from architecture.")
    return parser.parse_args()


def load_checkpoint(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")

    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        checkpoint = torch.load(path, map_location="cpu")

    if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
        raise ValueError(f"Unexpected checkpoint format in {path}")
    return checkpoint


def load_model(checkpoint_path: Path, classes_path: Path, device: torch.device):
    checkpoint = load_checkpoint(checkpoint_path)
    class_names = checkpoint.get("classes") or load_class_names(classes_path)
    architecture = checkpoint.get("architecture", "simple_cnn")
    image_size = checkpoint.get("image_size", 224)

    model = build_model(num_classes=len(class_names), architecture=architecture, pretrained=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    transform = build_inference_transform(image_size)
    return model, transform, class_names, architecture, image_size


def infer_image(image_path: Path, model: torch.nn.Module, transform, device: torch.device):
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    image = Image.open(image_path).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(tensor)
        probabilities = torch.softmax(logits, dim=1).squeeze(0).cpu().tolist()

    return probabilities


def format_results(probabilities: List[float], class_names: List[str], topk: int = 4) -> str:
    pairs = sorted(
        [(class_name, prob) for class_name, prob in zip(class_names, probabilities)],
        key=lambda item: item[1],
        reverse=True,
    )
    lines = ["Inference results:"]
    for rank, (class_name, probability) in enumerate(pairs[:topk], start=1):
        lines.append(f"{rank}. {class_name}: {probability * 100:.2f}%")
    lines.append(f"\nPredicted label: {pairs[0][0]}")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    model_path = args.model or DEFAULT_MODEL_PATH
    if not model_path.exists() and DEFAULT_FALLBACK_MODEL_PATH.exists():
        model_path = DEFAULT_FALLBACK_MODEL_PATH

    device = torch.device(args.device if torch.cuda.is_available() or args.device == "cpu" else "cpu")
    print(f"Using device: {device}")
    print(f"Loading model: {model_path}")

    model, transform, class_names, architecture, image_size = load_model(model_path, args.classes, device)
    print(f"Model architecture: {architecture}")
    print(f"Image size: {image_size}")
    print(f"Classes: {class_names}")

    probabilities = infer_image(args.image, model, transform, device)
    file_bytes = args.image.read_bytes()
    sha = hashlib.sha256(file_bytes).hexdigest()
    print(f"Input file SHA256: {sha}")
    print(format_results(probabilities, class_names, topk=args.topk))

    if args.gradcam:
        target_layer = args.target_layer or ("layer4" if architecture.startswith("resnet") else "features")
        print(f"Computing Grad-CAM (target layer: {target_layer})...")

        img = Image.open(args.image).convert("RGB")
        img_tensor = transform(img).unsqueeze(0).to(device)

        try:
            heatmap, pred_class = compute_gradcam(model, img_tensor, target_layer, device=device)
            overlay = visualize_gradcam_on_image(np.asarray(img.convert("L"), dtype=np.float32) / 255.0, heatmap, alpha=0.5, figsize=(6,6))

            out_path = args.image.with_name(args.image.stem + "_gradcam.png")
            overlay_img = (np.clip(overlay, 0, 1) * 255).astype(np.uint8)
            from PIL import Image as PILImage
            PILImage.fromarray(overlay_img).save(out_path.as_posix())
            print(f"Saved Grad-CAM overlay: {out_path}")
        except Exception as e:
            print(f"Grad-CAM error: {e}")


if __name__ == "__main__":
    main()
