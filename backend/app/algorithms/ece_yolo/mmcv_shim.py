"""Minimal mmcv.ops.ModulatedDeformConv2d compatibility layer.

ECE-YOLO's DynamicHead imports ``mmcv.ops.ModulatedDeformConv2d``.  Installing
real mmcv on Windows + torch 2.1 is painful, so this module provides the same
module/state-dict interface backed by torchvision's CUDA/CPU implementation.

The only behavioural difference that matters is output sizing: mmcv allocates
the output from input/stride/padding and indexes the offset at output
coordinates.  DynamicHead passes a larger offset map to the low-resolution
branch, so we crop to the output size before calling torchvision.
"""

import math
import sys
import types

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.ops import deform_conv2d

_SHIM_FLAG = "_ivap_mmcv_shim"


class ModulatedDeformConv2d(nn.Module):
    """Drop-in subset of ``mmcv.ops.ModulatedDeformConv2d``."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int = 1,
        padding: int = 0,
        dilation: int = 1,
        groups: int = 1,
        deform_groups: int = 1,
        bias: bool = True,
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = (kernel_size, kernel_size) if isinstance(kernel_size, int) else kernel_size
        self.stride = (stride, stride) if isinstance(stride, int) else stride
        self.padding = (padding, padding) if isinstance(padding, int) else padding
        self.dilation = (dilation, dilation) if isinstance(dilation, int) else dilation
        self.groups = groups
        self.deform_groups = deform_groups

        self.weight = nn.Parameter(
            torch.empty(out_channels, in_channels // groups, *self.kernel_size)
        )
        self.bias = nn.Parameter(torch.empty(out_channels)) if bias else None
        self.init_weights()

    def init_weights(self) -> None:
        n = self.in_channels
        for size in self.kernel_size:
            n *= size
        stdv = 1.0 / math.sqrt(n)
        self.weight.data.uniform_(-stdv, stdv)
        if self.bias is not None:
            self.bias.data.zero_()

    def forward(self, x: torch.Tensor, offset: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        if self.deform_groups != 1:
            raise NotImplementedError("compatibility shim supports deform_groups=1 only")

        kh, kw = self.weight.shape[2], self.weight.shape[3]
        out_h = (x.shape[2] + 2 * self.padding[0] - self.dilation[0] * (kh - 1) - 1) // self.stride[0] + 1
        out_w = (x.shape[3] + 2 * self.padding[1] - self.dilation[1] * (kw - 1) - 1) // self.stride[1] + 1

        if offset.shape[2] < out_h or offset.shape[3] < out_w:
            offset = F.interpolate(offset, size=(out_h, out_w), mode="bilinear", align_corners=False)
            mask = F.interpolate(mask, size=(out_h, out_w), mode="bilinear", align_corners=False)
        offset = offset[:, :, :out_h, :out_w].contiguous()
        mask = mask[:, :, :out_h, :out_w].contiguous()

        return deform_conv2d(
            x,
            offset,
            self.weight,
            self.bias,
            self.stride,
            self.padding,
            self.dilation,
            mask,
        )


def install_mmcv_shim() -> bool:
    """Register the shim if real mmcv is unavailable.

    Returns ``True`` when the shim was installed, ``False`` when real mmcv is
    importable (or the shim was already installed).
    """
    try:
        import mmcv.ops  # noqa: F401

        return False
    except Exception:
        pass

    if getattr(sys.modules.get("mmcv"), _SHIM_FLAG, False):
        return True

    mmcv = types.ModuleType("mmcv")
    mmcv.__path__ = []
    setattr(mmcv, _SHIM_FLAG, True)

    ops = types.ModuleType("mmcv.ops")
    ops.__path__ = []
    ops.ModulatedDeformConv2d = ModulatedDeformConv2d

    modulated = types.ModuleType("mmcv.ops.modulated_deform_conv")
    modulated.ModulatedDeformConv2d = ModulatedDeformConv2d
    ModulatedDeformConv2d.__module__ = "mmcv.ops.modulated_deform_conv"

    mmcv.ops = ops
    ops.modulated_deform_conv = modulated
    sys.modules["mmcv"] = mmcv
    sys.modules["mmcv.ops"] = ops
    sys.modules["mmcv.ops.modulated_deform_conv"] = modulated
    return True
