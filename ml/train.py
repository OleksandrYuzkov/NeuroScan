import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from torch import nn, optim
from torch.utils.data import DataLoader, Subset, WeightedRandomSampler
from torchvision.datasets import ImageFolder

from ml.model import (
    EFFICIENTNET_B4_IMAGE_SIZE,
    IMAGE_SIZE,
    build_inference_transform,
    build_model,
    build_train_transform,
    build_tta_transforms,
)
from ml.utils import save_class_names


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT_DIR / "data" / "brain_mri"
DEFAULT_MODELS_DIR = ROOT_DIR / "models"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train NeuroScan AI brain tumor classifier.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.00025)
    parser.add_argument("--backbone-learning-rate", type=float, default=0.000025)
    parser.add_argument("--architecture", type=str, default="resnet18")
    parser.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--label-smoothing", type=float, default=0.05)
    parser.add_argument("--class-weight-multiplier", type=float, default=1.0)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--warmup-epochs", type=int, default=3)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--min-delta", type=float, default=0.0005)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--tta", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--glioma-margin-grid",
        type=float,
        nargs="+",
        default=[0.0, 0.03, 0.05, 0.07, 0.1, 0.12, 0.15],
        help="Candidate margins for preferring glioma when its probability is close to the top class.",
    )
    parser.add_argument(
        "--selection-metric",
        choices=["accuracy", "macro_f1", "glioma_f1", "glioma_recall"],
        default="glioma_f1",
        help="Metric used to choose the best checkpoint during validation.",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def resolve_image_size(architecture: str) -> int:
    if architecture == "efficientnet_b4":
        return EFFICIENTNET_B4_IMAGE_SIZE
    return IMAGE_SIZE


def build_weighted_sampler(dataset: ImageFolder, indices: list[int]) -> WeightedRandomSampler:
    labels = [dataset.samples[index][1] for index in indices]
    class_counts = np.bincount(labels)
    class_weights = 1.0 / np.maximum(class_counts, 1)
    sample_weights = [float(class_weights[label]) for label in labels]
    return WeightedRandomSampler(sample_weights, num_samples=len(sample_weights), replacement=True)


class FocalLoss(nn.Module):
    def __init__(self, weight=None, gamma: float = 2.0, label_smoothing: float = 0.05) -> None:
        super().__init__()
        self.weight = weight
        self.gamma = gamma
        self.label_smoothing = label_smoothing

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = F.cross_entropy(
            inputs,
            targets,
            weight=self.weight,
            label_smoothing=self.label_smoothing,
            reduction="none",
        )
        pt = torch.exp(-ce)
        return (((1.0 - pt) ** self.gamma) * ce).mean()


def build_optimizer(model: nn.Module, args: argparse.Namespace) -> optim.Optimizer:
    classifier_params = []
    backbone_params = []

    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if name.startswith(("fc", "classifier")):
            classifier_params.append(parameter)
        else:
            backbone_params.append(parameter)

    return optim.AdamW(
        [
            {"params": backbone_params, "lr": args.backbone_learning_rate},
            {"params": classifier_params, "lr": args.learning_rate},
        ],
        weight_decay=0.01,
    )


def build_warmup_cosine_scheduler(optimizer: optim.Optimizer, args: argparse.Namespace):
    def lr_lambda(epoch: int) -> float:
        if epoch < args.warmup_epochs:
            return float(epoch + 1) / float(max(1, args.warmup_epochs))
        progress = (epoch - args.warmup_epochs) / float(max(1, args.epochs - args.warmup_epochs))
        return 0.08 + 0.92 * 0.5 * (1.0 + math.cos(math.pi * progress))

    return optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)


def train_one_epoch(model, dataloader, criterion, optimizer, device, grad_clip):
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in dataloader:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        if grad_clip > 0:
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=grad_clip)
        optimizer.step()

        running_loss += loss.item() * images.size(0)
        correct += (outputs.argmax(dim=1) == labels).sum().item()
        total += labels.size(0)

    return running_loss / total, correct / total


def evaluate(model, dataloader, criterion, device):
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    all_labels = []
    all_predictions = []

    with torch.no_grad():
        for images, labels in dataloader:
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            predictions = outputs.argmax(dim=1)

            running_loss += loss.item() * images.size(0)
            correct += (predictions == labels).sum().item()
            total += labels.size(0)
            all_labels.extend(labels.cpu().tolist())
            all_predictions.extend(predictions.cpu().tolist())

    return running_loss / total, correct / total, all_labels, all_predictions


def collect_outputs(model, dataloader, criterion, device):
    model.eval()
    running_loss = 0.0
    total = 0
    all_labels = []
    all_probabilities = []

    with torch.no_grad():
        for images, labels in dataloader:
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            probabilities = torch.softmax(outputs, dim=1)

            running_loss += loss.item() * images.size(0)
            total += labels.size(0)
            all_labels.extend(labels.cpu().tolist())
            all_probabilities.extend(probabilities.cpu().tolist())

    return running_loss / total, all_labels, np.array(all_probabilities, dtype=np.float32)


def predict_with_glioma_margin(probabilities: np.ndarray, class_names: list[str], margin: float) -> list[int]:
    predictions = probabilities.argmax(axis=1)
    if margin <= 0 or "glioma" not in class_names:
        return predictions.tolist()

    glioma_idx = class_names.index("glioma")
    max_probabilities = probabilities.max(axis=1)
    glioma_close = probabilities[:, glioma_idx] >= max_probabilities - margin
    predictions[glioma_close] = glioma_idx
    return predictions.tolist()


def tune_glioma_margin(
    labels: list[int],
    probabilities: np.ndarray,
    class_names: list[str],
    margins: list[float],
) -> tuple[float, float]:
    best_margin = 0.0
    best_score = -1.0

    for margin in margins:
        predictions = predict_with_glioma_margin(probabilities, class_names, margin)
        score = validation_score(labels, predictions, class_names, "glioma_f1", 0.0)
        if score > best_score:
            best_margin = float(margin)
            best_score = float(score)

    return best_margin, best_score


def validation_score(
    labels: list[int],
    predictions: list[int],
    class_names: list[str],
    metric: str,
    accuracy: float,
) -> float:
    if metric == "accuracy":
        return accuracy

    report = classification_report(
        labels,
        predictions,
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    if metric == "macro_f1":
        return float(report["macro avg"]["f1-score"])

    glioma_report = report.get("glioma")
    if glioma_report is None:
        raise ValueError("selection metric requires a 'glioma' class.")
    if metric == "glioma_f1":
        return float(glioma_report["f1-score"])
    if metric == "glioma_recall":
        return float(glioma_report["recall"])

    raise ValueError(f"Unknown selection metric: {metric}")


def evaluate_tta(model, dataset, device, image_size, glioma_margin: float):
    model.eval()
    tta_transforms = build_tta_transforms(image_size)
    correct = 0
    all_labels = []
    all_predictions = []

    with torch.no_grad():
        for image_path, label in dataset.samples:
            image = dataset.loader(image_path).convert("RGB")
            batch = torch.stack([transform(image) for transform in tta_transforms]).to(device)
            logits = model(batch).mean(dim=0)
            probabilities = torch.softmax(logits, dim=0)

            glioma_idx = dataset.classes.index("glioma")
            if probabilities[glioma_idx] >= probabilities.max() - glioma_margin:
                prediction = glioma_idx
            else:
                prediction = probabilities.argmax().item()

            correct += int(prediction == label)
            all_labels.append(label)
            all_predictions.append(prediction)

    return correct / len(dataset), all_labels, all_predictions


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    image_size = resolve_image_size(args.architecture)

    train_dir = args.data_dir / "Training"
    test_dir = args.data_dir / "Testing"

    print(f"Dataset folder: {args.data_dir}")
    print(f"Training folder: {train_dir}")
    print(f"Testing folder: {test_dir}")
    print(f"Models folder: {args.output_dir}")

    if not args.data_dir.exists():
        raise FileNotFoundError(f"Dataset folder not found: {args.data_dir}.")
    if not train_dir.exists() or not test_dir.exists():
        raise FileNotFoundError(f"Expected Training and Testing folders in {args.data_dir}.")

    train_source = ImageFolder(train_dir, transform=build_train_transform(image_size))
    validation_source = ImageFolder(train_dir, transform=build_inference_transform(image_size))
    test_dataset = ImageFolder(test_dir, transform=build_inference_transform(image_size))

    print(f"Classes: {train_source.classes}")
    print(f"Training images: {len(train_source)}")
    print(f"Testing images: {len(test_dataset)}")

    if train_source.classes != test_dataset.classes:
        raise ValueError(
            f"Training classes {train_source.classes} do not match Testing classes {test_dataset.classes}."
        )

    all_indices = list(range(len(train_source)))
    all_labels = [train_source.samples[index][1] for index in all_indices]
    train_indices, validation_indices = train_test_split(
        all_indices,
        test_size=args.val_ratio,
        random_state=args.seed,
        stratify=all_labels,
    )

    train_dataset = Subset(train_source, train_indices)
    validation_dataset = Subset(validation_source, validation_indices)
    sampler = build_weighted_sampler(train_source, train_indices)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, sampler=sampler)
    validation_loader = DataLoader(validation_dataset, batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Architecture: {args.architecture}")
    print(f"Pretrained weights: {args.pretrained}")
    print(f"Image size: {image_size}")
    print(f"Validation images: {len(validation_dataset)}")
    print(f"Selection metric: {args.selection_metric}")

    model = build_model(
        num_classes=len(train_source.classes),
        architecture=args.architecture,
        pretrained=args.pretrained,
    ).to(device)

    train_labels = [train_source.samples[index][1] for index in train_indices]
    class_counts = np.bincount(train_labels, minlength=len(train_source.classes))
    class_weights = 1.0 / np.maximum(class_counts, 1)
    if "glioma" in train_source.classes:
        glioma_idx = train_source.classes.index("glioma")
        class_weights[glioma_idx] *= float(args.class_weight_multiplier)
    class_weights = class_weights / float(np.mean(class_weights))
    weights_tensor = torch.tensor(class_weights, dtype=torch.float32).to(device)

    print(f"Class counts: {dict(zip(train_source.classes, class_counts))}")
    print(f"Class weights: {dict(zip(train_source.classes, [float(round(w, 4)) for w in class_weights]))}")

    criterion = FocalLoss(weight=weights_tensor, gamma=2.0, label_smoothing=args.label_smoothing)
    optimizer = build_optimizer(model, args)
    scheduler = build_warmup_cosine_scheduler(optimizer, args)

    best_score = 0.0
    best_accuracy = 0.0
    best_epoch = 0
    epochs_without_improvement = 0
    history = []
    model_filename = f"brain_tumor_{args.architecture}.pt"
    metrics_filename = f"metrics_{args.architecture}.json"

    for epoch in range(1, args.epochs + 1):
        train_loss, train_accuracy = train_one_epoch(
            model, train_loader, criterion, optimizer, device, args.grad_clip
        )
        validation_loss, validation_accuracy, validation_labels, validation_predictions = evaluate(
            model, validation_loader, criterion, device
        )
        current_score = validation_score(
            validation_labels,
            validation_predictions,
            train_source.classes,
            args.selection_metric,
            validation_accuracy,
        )
        current_backbone_lr = optimizer.param_groups[0]["lr"]
        current_classifier_lr = optimizer.param_groups[1]["lr"]

        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "train_accuracy": train_accuracy,
                "validation_loss": validation_loss,
                "validation_accuracy": validation_accuracy,
                args.selection_metric: current_score,
                "backbone_lr": current_backbone_lr,
                "classifier_lr": current_classifier_lr,
            }
        )
        print(
            f"Epoch {epoch:02d}: train_acc={train_accuracy:.4f}, "
            f"val_acc={validation_accuracy:.4f}, val_loss={validation_loss:.4f}, "
            f"{args.selection_metric}={current_score:.4f}, "
            f"lr={current_backbone_lr:.7f}/{current_classifier_lr:.7f}"
        )

        if current_score > best_score + args.min_delta:
            best_score = current_score
            best_accuracy = validation_accuracy
            best_epoch = epoch
            epochs_without_improvement = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "classes": train_source.classes,
                    "architecture": args.architecture,
                    "image_size": image_size,
                    "validation_accuracy": best_accuracy,
                    "selection_metric": args.selection_metric,
                    "selection_score": best_score,
                },
                args.output_dir / model_filename,
            )
        else:
            epochs_without_improvement += 1

        scheduler.step()
        if epochs_without_improvement >= args.patience:
            print(f"Early stopping after {epoch} epochs. Best epoch: {best_epoch}")
            break

    save_class_names(args.output_dir / "classes.json", train_source.classes)
    best_checkpoint = torch.load(args.output_dir / model_filename, map_location=device, weights_only=True)
    model.load_state_dict(best_checkpoint["model_state_dict"])

    _, margin_labels, margin_probabilities = collect_outputs(model, validation_loader, criterion, device)
    best_glioma_margin, best_margin_score = tune_glioma_margin(
        margin_labels,
        margin_probabilities,
        train_source.classes,
        args.glioma_margin_grid,
    )
    print(f"Best glioma margin: {best_glioma_margin:.2f} (validation glioma_f1={best_margin_score:.4f})")

    test_loss, labels, test_probabilities = collect_outputs(model, test_loader, criterion, device)
    predictions = predict_with_glioma_margin(test_probabilities, train_source.classes, best_glioma_margin)
    test_accuracy = float(np.mean(np.array(predictions) == np.array(labels)))
    tta_accuracy = None
    if args.tta:
        tta_accuracy, labels, predictions = evaluate_tta(
            model,
            test_dataset,
            device,
            image_size,
            best_glioma_margin,
        )
        print(f"Final TTA test accuracy: {tta_accuracy:.4f}")

    report = classification_report(
        labels,
        predictions,
        target_names=train_source.classes,
        output_dict=True,
        zero_division=0,
    )
    metrics = {
        "best_validation_accuracy": best_accuracy,
        "best_selection_metric": args.selection_metric,
        "best_selection_score": best_score,
        "best_glioma_margin": best_glioma_margin,
        "best_glioma_margin_validation_f1": best_margin_score,
        "best_epoch": best_epoch,
        "final_test_accuracy": test_accuracy,
        "final_test_loss": test_loss,
        "final_tta_test_accuracy": tta_accuracy,
        "classes": train_source.classes,
        "history": history,
        "classification_report": report,
        "confusion_matrix": confusion_matrix(labels, predictions).tolist(),
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / metrics_filename).write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    shutil.copyfile(args.output_dir / model_filename, args.output_dir / "brain_tumor_cnn.pt")
    print(f"Saved model to {args.output_dir / model_filename}")
    print(f"Updated active model: {args.output_dir / 'brain_tumor_cnn.pt'}")
    print(f"Best validation accuracy: {best_accuracy:.4f}")
    print(f"Best {args.selection_metric}: {best_score:.4f}")
    print(f"Final test accuracy: {test_accuracy:.4f}")


if __name__ == "__main__":
    main()
