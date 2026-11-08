import torch
import torch.nn as nn
from ultralytics.nn.modules.conv import Conv

__all__ = ['ESPMStem']


class ESPMStem(nn.Module):
    """
    ESPMStem: Spatial-Preserving Modulation Stem
    Drop-in replacement for the first Conv layer in YOLO11

    Args:
        c1 (int): input channels
        c2 (int): output channels
        alpha (float): fixed spatial gating ratio (0 < alpha <= 1)
    """

    def __init__(self, c1, c2, alpha=0.5):
        super().__init__()
        assert 0 < alpha <= 1.0, "alpha must be in (0, 1]"

        self.alpha = alpha

        # 1️⃣ High-resolution spatial modeling (no downsampling)
        self.pre = Conv(c1, c2, k=3, s=1)

        # 2️⃣ Learnable spatial gate (importance-aware)
        self.spatial_gate = nn.Sequential(
            nn.Conv2d(c2, 1, kernel_size=1, bias=True),
            nn.Sigmoid()
        )

        # 3️⃣ Downsampling after spatial modulation
        self.down = Conv(c2, c2, k=3, s=2)

    def forward(self, x):
        # Preserve spatial details
        x = self.pre(x)

        # Learn spatial importance map
        gate = self.spatial_gate(x)      # [B, 1, H, W]

        # Fixed-ratio spatial modulation
        x = x * (self.alpha * gate)

        # Controlled downsampling
        x = self.down(x)

        return x
