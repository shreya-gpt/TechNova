"""
Landslide Segmentation stage — model definition.

Model choice rationale (see docs/architecture.md for the full comparison):

  U-Net            <- RECOMMENDED for the hackathon MVP
  DeepLabV3+
  SegFormer
  Siamese/change-detection nets

U-Net is recommended because: (1) it trains well on small/scarce labeled
datasets thanks to its symmetric skip connections, which is exactly the
regime a hackathon team is in; (2) it is lightweight enough to train and run
inference on a single GPU or even CPU within a hackathon's time budget;
(3) it has abundant reference implementations/tutorials for remote-sensing
segmentation, reducing implementation risk; (4) its precise boundary
localisation suits the elongated, irregular shapes typical of landslide
scars better than a lower-resolution transformer decoder would, at MVP data
scale. DeepLabV3+/SegFormer are noted as natural upgrades once more labeled
data and compute become available post-hackathon.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class DoubleConv(nn.Module):
    """(Conv2d -> BatchNorm -> ReLU) x2 — the basic U-Net building block."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class UNet(nn.Module):
    """
    Compact U-Net for binary landslide segmentation.

    Input:  (B, in_channels, H, W) — stacked optical bands + spectral indices
             (e.g. RGB, NIR, SWIR1/2, NDVI, NDWI, BSI — configurable via
             `in_channels`; see config.yaml `segmentation.in_channels`).
    Output: (B, 1, H, W) raw logits — apply sigmoid for a 0..1 probability
             map, then threshold (config `segmentation.probability_threshold`)
             for a binary landslide mask.
    """

    def __init__(self, in_channels: int = 6, num_classes: int = 1, base_channels: int = 32):
        super().__init__()
        c = base_channels

        self.enc1 = DoubleConv(in_channels, c)
        self.enc2 = DoubleConv(c, c * 2)
        self.enc3 = DoubleConv(c * 2, c * 4)
        self.enc4 = DoubleConv(c * 4, c * 8)

        self.pool = nn.MaxPool2d(2)

        self.bottleneck = DoubleConv(c * 8, c * 16)

        self.up4 = nn.ConvTranspose2d(c * 16, c * 8, kernel_size=2, stride=2)
        self.dec4 = DoubleConv(c * 16, c * 8)
        self.up3 = nn.ConvTranspose2d(c * 8, c * 4, kernel_size=2, stride=2)
        self.dec3 = DoubleConv(c * 8, c * 4)
        self.up2 = nn.ConvTranspose2d(c * 4, c * 2, kernel_size=2, stride=2)
        self.dec2 = DoubleConv(c * 4, c * 2)
        self.up1 = nn.ConvTranspose2d(c * 2, c, kernel_size=2, stride=2)
        self.dec1 = DoubleConv(c * 2, c)

        self.out_conv = nn.Conv2d(c, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))

        b = self.bottleneck(self.pool(e4))

        d4 = self.up4(b)
        d4 = self.dec4(torch.cat([d4, e4], dim=1))
        d3 = self.up3(d4)
        d3 = self.dec3(torch.cat([d3, e3], dim=1))
        d2 = self.up2(d3)
        d2 = self.dec2(torch.cat([d2, e2], dim=1))
        d1 = self.up1(d2)
        d1 = self.dec1(torch.cat([d1, e1], dim=1))

        return self.out_conv(d1)


def load_model(checkpoint_path: str | None, in_channels: int = 6, device: str = "cpu") -> UNet:
    """Instantiate a UNet and optionally load trained weights from disk."""
    model = UNet(in_channels=in_channels)
    if checkpoint_path:
        try:
            state_dict = torch.load(checkpoint_path, map_location=device)
            model.load_state_dict(state_dict)
        except FileNotFoundError:
            # No trained checkpoint yet — return randomly-initialized weights so
            # the pipeline is still runnable end-to-end before training finishes.
            pass
    model.to(device)
    model.eval()
    return model
