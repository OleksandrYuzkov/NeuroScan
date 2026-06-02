from pathlib import Path
import random
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from PIL import Image, ImageEnhance


def apply_windowing(arr: np.ndarray, center: int, width: int) -> np.ndarray:
    lo = center - width // 2
    hi = center + width // 2
    out = np.clip(arr.astype(np.float32), lo, hi)
    out = (out - lo) / (hi - lo)
    return out


def enhance_mri(img: Image.Image, center: int = 128, width: int = 200,
                contrast: float = 1.4, sharpness: float = 1.6) -> Image.Image:
    img = img.convert("L")
    arr = np.asarray(img, dtype=np.float32)
    arr = apply_windowing(arr, center, width)
    enhanced = Image.fromarray((arr * 255).astype(np.uint8))
    enhanced = ImageEnhance.Contrast(enhanced).enhance(contrast)
    enhanced = ImageEnhance.Sharpness(enhanced).enhance(sharpness)
    return enhanced


def img_stats(img: Image.Image) -> dict:
    arr = np.asarray(img.convert("L"), dtype=np.float32)
    return {"mean": arr.mean(), "std": arr.std(), "min": arr.min(), "max": arr.max()}


def visualize_mri_samples(data_dir: Path, samples_per_class: int = 5, seed: int = 42,
                          center: int = 128, width: int = 200):
    random.seed(seed)
    class_dirs = sorted(p for p in (Path(data_dir) / "Training").iterdir() if p.is_dir())
    n_classes = len(class_dirs)

    palette = ["#1D9E75", "#D85A30", "#378ADD", "#BA7517",
               "#8B5CF6", "#EC4899", "#14B8A6", "#F59E0B"]
    class_colors = {cd.name: palette[i % len(palette)] for i, cd in enumerate(class_dirs)}

    fig = plt.figure(figsize=(samples_per_class * 2.6, n_classes * 3.0 + 1.5), facecolor="#0d0d0d")
    outer = gridspec.GridSpec(n_classes, 1, figure=fig, hspace=0.38, top=0.93, bottom=0.04, left=0.10, right=0.98)

    fig.suptitle("Brain MRI — sample overview", color="white", fontsize=16, fontweight="bold", x=0.54, y=0.98)

    for row_idx, class_dir in enumerate(class_dirs):
        images = [p for p in class_dir.iterdir() if p.is_file()]
        selected = random.sample(images, k=min(samples_per_class, len(images)))

        inner = gridspec.GridSpecFromSubplotSpec(1, samples_per_class, subplot_spec=outer[row_idx], wspace=0.06)
        color = class_colors[class_dir.name]

        label_ax = fig.add_axes([0.0, 0.0, 1, 1], frameon=False)
        label_ax.set_xlim(0, 1); label_ax.set_ylim(0, 1); label_ax.axis("off")
        ss = outer[row_idx].get_position(fig); mid_y = (ss.y0 + ss.y1) / 2
        label_ax.text(0.01, mid_y, class_dir.name.upper(), color=color, fontsize=9, fontweight="bold", rotation=90, va="center", ha="center", transform=fig.transFigure)

        for col_idx in range(samples_per_class):
            ax = fig.add_subplot(inner[col_idx]); ax.set_facecolor("#0d0d0d")
            if col_idx < len(selected):
                img = Image.open(selected[col_idx])
                img_enh = enhance_mri(img, center=center, width=width)
                stats = img_stats(img)
                ax.imshow(img_enh, cmap="gray", vmin=0, vmax=255, interpolation="lanczos")
                ax.text(0.97, 0.97, f"#{col_idx + 1}", transform=ax.transAxes, color="white", fontsize=7, alpha=0.55, ha="right", va="top")
                ax.text(0.03, 0.04, f"μ={stats['mean']:.0f}", transform=ax.transAxes, color=color, fontsize=6.5, alpha=0.85, ha="left", va="bottom", fontfamily="monospace")
            else:
                ax.text(0.5, 0.5, "—", transform=ax.transAxes, color="#555", fontsize=18, ha="center", va="center")

            spine_color = color if col_idx == 0 else "#2a2a2a"
            lw = 1.4 if col_idx == 0 else 0.5
            for spine in ax.spines.values():
                spine.set_edgecolor(spine_color); spine.set_linewidth(lw)
            ax.set_xticks([]); ax.set_yticks([])

    out = Path.cwd() / "mri_samples_enhanced.png"
    plt.savefig(out.as_posix(), dpi=160, bbox_inches="tight", facecolor="#0d0d0d")
    plt.show()
    print(f"Збережено: {out}")


def visualize_enhancement_comparison(data_dir: Path, n_samples: int = 4, seed: int = 42,
                                     center: int = 128, width: int = 200):
    random.seed(seed)
    class_dirs = sorted(p for p in (Path(data_dir) / "Training").iterdir() if p.is_dir())
    palette = ["#1D9E75", "#D85A30", "#378ADD", "#BA7517"]

    fig, axes = plt.subplots(len(class_dirs), n_samples * 2, figsize=(n_samples * 4.2, len(class_dirs) * 2.4), facecolor="#0d0d0d")
    if len(class_dirs) == 1:
        axes = np.array([axes])

    fig.suptitle("Original  ↔  Enhanced (window/level + sharpness)", color="white", fontsize=13, fontweight="bold", y=1.01)

    for row, class_dir in enumerate(class_dirs):
        images = [p for p in class_dir.iterdir() if p.is_file()]
        selected = random.sample(images, k=min(n_samples, len(images)))
        color = palette[row % len(palette)]

        for col, path in enumerate(selected):
            img_orig = Image.open(path).convert("L")
            img_enh = enhance_mri(img_orig, center=center, width=width)
            ax_o = axes[row, col * 2]
            ax_o.imshow(img_orig, cmap="gray", vmin=0, vmax=255)
            ax_o.set_xticks([]); ax_o.set_yticks([]); ax_o.set_facecolor("#0d0d0d")
            if col == 0:
                ax_o.set_ylabel(class_dir.name, color=color, fontsize=8, fontweight="bold")
            if row == 0:
                ax_o.set_title("Original", color="#aaa", fontsize=8)
            for sp in ax_o.spines.values():
                sp.set_edgecolor("#333"); sp.set_linewidth(0.6)

            ax_e = axes[row, col * 2 + 1]
            ax_e.imshow(img_enh, cmap="gray", vmin=0, vmax=255)
            ax_e.set_xticks([]); ax_e.set_yticks([]); ax_e.set_facecolor("#0d0d0d")
            if row == 0:
                ax_e.set_title("Enhanced", color=color, fontsize=8, fontweight="bold")
            for sp in ax_e.spines.values():
                sp.set_edgecolor(color); sp.set_linewidth(0.9)

    out = Path.cwd() / "mri_comparison.png"
    plt.tight_layout(); plt.savefig(out.as_posix(), dpi=160, bbox_inches="tight", facecolor="#0d0d0d")
    plt.show()
    print(f"Збережено: {out}")


def visualize_false_negatives(class_name: str = "glioma", reports_dir: Path = None, n_cols: int = 6,
                              seed: int = 42, center: int = 128, width: int = 200):
    random.seed(seed)
    if reports_dir is None:
        reports_dir = Path.cwd() / "reports" / "false_negatives"
    imgs_dir = Path(reports_dir) / class_name
    if not imgs_dir.exists():
        fallback = Path.cwd() / "data" / "brain_mri" / "Testing" / class_name
        if fallback.exists():
            imgs_dir = fallback
        else:
            print(f"No false-negative folder or fallback found for class: {class_name}")
            return

    images = sorted([p for p in imgs_dir.iterdir() if p.is_file()])
    if len(images) == 0:
        print(f"No images found in {imgs_dir}")
        return

    n = min(len(images), n_cols * 3)
    rows = (n + n_cols - 1) // n_cols

    fig, axes = plt.subplots(rows, n_cols, figsize=(n_cols * 2.2, rows * 2.2), facecolor="#0d0d0d")
    if rows == 1 and n_cols == 1:
        axes = np.array([[axes]])
    axes = np.atleast_2d(axes)

    for i in range(rows * n_cols):
        r = i // n_cols; c = i % n_cols
        ax = axes[r, c]
        ax.set_facecolor("#0d0d0d"); ax.set_xticks([]); ax.set_yticks([])

        if i < n:
            path = images[i]
            img = Image.open(path).convert("L")
            img_enh = enhance_mri(img, center=center, width=width)
            ax.imshow(img_enh, cmap="gray", vmin=0, vmax=255)
            name = path.name
            ax.set_title(name, fontsize=7, color="#fff")
        else:
            ax.text(0.5, 0.5, "—", color="#555", ha="center", va="center", fontsize=12)

        for sp in ax.spines.values():
            sp.set_edgecolor("#333"); sp.set_linewidth(0.6)

    out_name = Path.cwd() / f"mri_false_negatives_{class_name}.png"
    plt.tight_layout(); plt.savefig(out_name.as_posix(), dpi=160, bbox_inches="tight", facecolor="#0d0d0d")
    plt.show()
    print(f"Збережено: {out_name}  (showing {n} images from {imgs_dir})")


def compute_gradcam(model, image_tensor, target_layer_name: str, device="cuda"):
    """Compute Grad-CAM heatmap for an image."""
    import torch
    
    model.eval()
    
    target_layer = dict(model.named_modules())[target_layer_name]

    activations = []
    gradients = []
    
    def forward_hook(module, input, output):
        activations.append(output.detach())
    
    def backward_hook(module, grad_input, grad_output):
        gradients.append(grad_output[0].detach())
    
    forward_handle = target_layer.register_forward_hook(forward_hook)
    backward_handle = target_layer.register_backward_hook(backward_hook)
    
    try:
        image_tensor = image_tensor.to(device)
        output = model(image_tensor)
        target_class = output.argmax(dim=1)
        
        model.zero_grad()
        
        class_loss = output[0, target_class]
        class_loss.backward()
        
        activations_batch = activations[0][0]  # (C, H, W)
        gradients_batch = gradients[0][0]      # (C, H, W)
        
        weights = gradients_batch.mean(dim=(1, 2))  # (C,)
        cam = (weights.view(-1, 1, 1) * activations_batch).sum(dim=0)  # (H, W)
        
        cam = torch.relu(cam)
        cam_min, cam_max = cam.min(), cam.max()
        if cam_max > cam_min:
            cam = (cam - cam_min) / (cam_max - cam_min)
        
        return cam.cpu().numpy(), target_class.item()
    finally:
        forward_handle.remove()
        backward_handle.remove()


def visualize_gradcam_on_image(image_arr: np.ndarray, heatmap: np.ndarray, 
                               alpha: float = 0.4, figsize=(8, 8)):
    """Overlay Grad-CAM heatmap on image and display."""
    import matplotlib.cm as cm
    
    if len(image_arr.shape) == 3:
        image_arr = image_arr.mean(axis=2)
    
    from scipy.ndimage import zoom
    if heatmap.shape != image_arr.shape:
        scale = tuple(np.array(image_arr.shape) / np.array(heatmap.shape))
        heatmap_resized = zoom(heatmap, scale, order=1)
    else:
        heatmap_resized = heatmap
    
    img_norm = (image_arr - image_arr.min()) / (image_arr.max() - image_arr.min() + 1e-6)
    heat_norm = (heatmap_resized - heatmap_resized.min()) / (heatmap_resized.max() - heatmap_resized.min() + 1e-6)
    
    jet = cm.get_cmap("jet")
    heat_colored = jet(heat_norm)[:, :, :3]  # RGB only
    
    overlay = heat_colored * alpha + np.stack([img_norm]*3, axis=2) * (1 - alpha)
    
    plt.figure(figsize=figsize)
    plt.imshow(overlay, cmap="gray")
    plt.axis("off")
    plt.tight_layout()
    plt.show()
    
    return overlay
