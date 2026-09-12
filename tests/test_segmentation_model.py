import torch

from src.segmentation.model import UNet, load_model


def test_unet_forward_shape():
    model = UNet(in_channels=6, num_classes=1, base_channels=8)
    model.eval()
    x = torch.randn(2, 6, 64, 64)
    with torch.no_grad():
        out = model(x)
    assert out.shape == (2, 1, 64, 64)


def test_unet_output_is_finite():
    model = UNet(in_channels=6, base_channels=8)
    model.eval()
    x = torch.randn(1, 6, 32, 32)
    with torch.no_grad():
        out = model(x)
    assert torch.isfinite(out).all()


def test_load_model_without_checkpoint_returns_usable_model():
    model = load_model(checkpoint_path=None, in_channels=6)
    assert isinstance(model, UNet)
    x = torch.randn(1, 6, 32, 32)
    with torch.no_grad():
        out = model(x)
    assert out.shape == (1, 1, 32, 32)


def test_load_model_missing_checkpoint_path_degrades_gracefully():
    model = load_model(checkpoint_path="data/models/does_not_exist.pt", in_channels=6)
    assert isinstance(model, UNet)
