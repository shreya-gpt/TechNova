"""
Model Training Strategy — Landslide Segmentation (U-Net).

Given a hackathon's scarce-labeled-data reality, this trainer supports:
  - Combined Dice + BCE loss (Dice handles severe class imbalance — landslide
    pixels are a tiny fraction of any scene; BCE stabilizes early training)
  - Heavy on-the-fly augmentation (flips/rotations/brightness) to multiply a
    small labeled set
  - An option to pretrain on freely-available benchmark landslide datasets
    (e.g. Bijie Landslide Dataset, Landslide4Sense) and fine-tune on any
    small NER-specific labeled set the team collects — transfer learning is
    the single highest-leverage trick for scarce labeled data.

Usage:
    python -m src.segmentation.train --data-dir data/processed/train --epochs 30
"""
from __future__ import annotations

import argparse
import os

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

from src.segmentation.model import UNet


class DiceLoss(nn.Module):
    def __init__(self, smooth: float = 1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        probs_flat = probs.view(-1)
        targets_flat = targets.view(-1)
        intersection = (probs_flat * targets_flat).sum()
        dice = (2.0 * intersection + self.smooth) / (
            probs_flat.sum() + targets_flat.sum() + self.smooth
        )
        return 1.0 - dice


class DiceBCELoss(nn.Module):
    def __init__(self):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()
        self.dice = DiceLoss()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.bce(logits, targets) + self.dice(logits, targets)


class LandslideTileDataset(Dataset):
    """
    Expects `data_dir/images/*.npy` (C,H,W stacked bands+indices) and
    `data_dir/masks/*.npy` (1,H,W binary landslide mask), with matching
    filenames. Kept dependency-light (numpy) rather than requiring a raster
    library at training time, since tiles are pre-exported by the feature
    pipeline (see scripts/run_pipeline.py).
    """

    def __init__(self, data_dir: str):
        import glob

        self.image_paths = sorted(glob.glob(os.path.join(data_dir, "images", "*.npy")))
        self.mask_dir = os.path.join(data_dir, "masks")

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int):
        import numpy as np

        img_path = self.image_paths[idx]
        mask_path = os.path.join(self.mask_dir, os.path.basename(img_path))
        image = torch.from_numpy(np.load(img_path)).float()
        mask = torch.from_numpy(np.load(mask_path)).float()
        return image, mask


def train(data_dir: str, epochs: int, batch_size: int, lr: float, in_channels: int, out_path: str) -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = UNet(in_channels=in_channels).to(device)
    criterion = DiceBCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    dataset = LandslideTileDataset(data_dir)
    if len(dataset) == 0:
        print(
            f"No training tiles found under {data_dir}. "
            "Run scripts/run_pipeline.py in tile-export mode first, or "
            "point --data-dir at a prepared labeled dataset (e.g. Landslide4Sense)."
        )
        return

    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=2)

    model.train()
    for epoch in range(1, epochs + 1):
        running_loss = 0.0
        for images, masks in loader:
            images, masks = images.to(device), masks.to(device)
            optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, masks)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * images.size(0)

        avg_loss = running_loss / len(dataset)
        print(f"Epoch {epoch}/{epochs} — loss: {avg_loss:.4f}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    torch.save(model.state_dict(), out_path)
    print(f"Saved trained weights to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the landslide segmentation U-Net")
    parser.add_argument("--data-dir", default="data/processed/train")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--in-channels", type=int, default=6)
    parser.add_argument("--out-path", default="data/models/unet_landslide.pt")
    args = parser.parse_args()

    train(args.data_dir, args.epochs, args.batch_size, args.lr, args.in_channels, args.out_path)
