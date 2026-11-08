# import torch
# import torch.nn as nn
# import numpy as np
#
# __all__ = ['RepNCSPELAN4_low', 'RepNCSPELAN4_high']
#
#
# class RepConvN(nn.Module):
#     """RepConv is a basic rep-style block, including training and deploy status
#     This code is based on https://github.com/DingXiaoH/RepVGG/blob/main/repvgg.py
#     """
#     default_act = nn.SiLU()  # default activation
#
#     def __init__(self, c1, c2, k=3, s=1, p=1, g=1, d=1, act=True, bn=False, deploy=False):
#         super().__init__()
#         assert k == 3 and p == 1
#         self.g = g
#         self.c1 = c1
#         self.c2 = c2
#         self.act = self.default_act if act is True else act if isinstance(act, nn.Module) else nn.Identity()
#
#         self.bn = None
#         self.conv1 = Conv(c1, c2, k, s, p=p, g=g, act=False)
#         self.conv2 = Conv(c1, c2, 1, s, p=(p - k // 2), g=g, act=False)
#
#     def forward_fuse(self, x):
#         """Forward process"""
#         return self.act(self.conv(x))
#
#     def forward(self, x):
#         """Forward process"""
#         id_out = 0 if self.bn is None else self.bn(x)
#         return self.act(self.conv1(x) + self.conv2(x) + id_out)
#
#     def get_equivalent_kernel_bias(self):
#         kernel3x3, bias3x3 = self._fuse_bn_tensor(self.conv1)
#         kernel1x1, bias1x1 = self._fuse_bn_tensor(self.conv2)
#         kernelid, biasid = self._fuse_bn_tensor(self.bn)
#         return kernel3x3 + self._pad_1x1_to_3x3_tensor(kernel1x1) + kernelid, bias3x3 + bias1x1 + biasid
#
#     def _avg_to_3x3_tensor(self, avgp):
#         channels = self.c1
#         groups = self.g
#         kernel_size = avgp.kernel_size
#         input_dim = channels // groups
#         k = torch.zeros((channels, input_dim, kernel_size, kernel_size))
#         k[np.arange(channels), np.tile(np.arange(input_dim), groups), :, :] = 1.0 / kernel_size ** 2
#         return k
#
#     def _pad_1x1_to_3x3_tensor(self, kernel1x1):
#         if kernel1x1 is None:
#             return 0
#         else:
#             return torch.nn.functional.pad(kernel1x1, [1, 1, 1, 1])
#
#     def _fuse_bn_tensor(self, branch):
#         if branch is None:
#             return 0, 0
#         if isinstance(branch, Conv):
#             kernel = branch.conv.weight
#             running_mean = branch.bn.running_mean
#             running_var = branch.bn.running_var
#             gamma = branch.bn.weight
#             beta = branch.bn.bias
#             eps = branch.bn.eps
#         elif isinstance(branch, nn.BatchNorm2d):
#             if not hasattr(self, 'id_tensor'):
#                 input_dim = self.c1 // self.g
#                 kernel_value = np.zeros((self.c1, input_dim, 3, 3), dtype=np.float32)
#                 for i in range(self.c1):
#                     kernel_value[i, i % input_dim, 1, 1] = 1
#                 self.id_tensor = torch.from_numpy(kernel_value).to(branch.weight.device)
#             kernel = self.id_tensor
#             running_mean = branch.running_mean
#             running_var = branch.running_var
#             gamma = branch.weight
#             beta = branch.bias
#             eps = branch.eps
#         std = (running_var + eps).sqrt()
#         t = (gamma / std).reshape(-1, 1, 1, 1)
#         return kernel * t, beta - running_mean * gamma / std
#
#     def fuse_convs(self):
#         if hasattr(self, 'conv'):
#             return
#         kernel, bias = self.get_equivalent_kernel_bias()
#         self.conv = nn.Conv2d(in_channels=self.conv1.conv.in_channels,
#                               out_channels=self.conv1.conv.out_channels,
#                               kernel_size=self.conv1.conv.kernel_size,
#                               stride=self.conv1.conv.stride,
#                               padding=self.conv1.conv.padding,
#                               dilation=self.conv1.conv.dilation,
#                               groups=self.conv1.conv.groups,
#                               bias=True).requires_grad_(False)
#         self.conv.weight.data = kernel
#         self.conv.bias.data = bias
#         for para in self.parameters():
#             para.detach_()
#         self.__delattr__('conv1')
#         self.__delattr__('conv2')
#         if hasattr(self, 'nm'):
#             self.__delattr__('nm')
#         if hasattr(self, 'bn'):
#             self.__delattr__('bn')
#         if hasattr(self, 'id_tensor'):
#             self.__delattr__('id_tensor')
#
#
# class RepNBottleneck(nn.Module):
#     # Standard bottleneck
#     def __init__(self, c1, c2, shortcut=True, g=1, k=(3, 3), e=0.5):  # ch_in, ch_out, shortcut, kernels, groups, expand
#         super().__init__()
#         c_ = int(c2 * e)  # hidden channels
#         self.cv1 = RepConvN(c1, c_, k[0], 1)
#         self.cv2 = Conv(c_, c2, k[1], 1, g=g)
#         self.add = shortcut and c1 == c2
#
#     def forward(self, x):
#         return x + self.cv2(self.cv1(x)) if self.add else self.cv2(self.cv1(x))
#
#
# class RepNCSP(nn.Module):
#     # CSP Bottleneck with 3 convolutions
#     def __init__(self, c1, c2, n=1, shortcut=True, g=1, e=0.5):  # ch_in, ch_out, number, shortcut, groups, expansion
#         super().__init__()
#         c_ = int(c2 * e)  # hidden channels
#         self.cv1 = Conv(c1, c_, 1, 1)
#         self.cv2 = Conv(c1, c_, 1, 1)
#         self.cv3 = Conv(2 * c_, c2, 1)  # optional act=FReLU(c2)
#         self.m = nn.Sequential(*(RepNBottleneck(c_, c_, shortcut, g, e=1.0) for _ in range(n)))
#
#     def forward(self, x):
#         return self.cv3(torch.cat((self.m(self.cv1(x)), self.cv2(x)), 1))
#
#
# def autopad(k, p=None, d=1):  # kernel, padding, dilation
#     # Pad to 'same' shape outputs
#     if d > 1:
#         k = d * (k - 1) + 1 if isinstance(k, int) else [d * (x - 1) + 1 for x in k]  # actual kernel-size
#     if p is None:
#         p = k // 2 if isinstance(k, int) else [x // 2 for x in k]  # auto-pad
#     return p
#
#
# class Conv(nn.Module):
#     # Standard convolution with args(ch_in, ch_out, kernel, stride, padding, groups, dilation, activation)
#     default_act = nn.SiLU()  # default activation
#
#     def __init__(self, c1, c2, k=1, s=1, p=None, g=1, d=1, act=True):
#         super().__init__()
#         self.conv = nn.Conv2d(c1, c2, k, s, autopad(k, p, d), groups=g, dilation=d, bias=False)
#         self.bn = nn.BatchNorm2d(c2)
#         self.act = self.default_act if act is True else act if isinstance(act, nn.Module) else nn.Identity()
#
#     def forward(self, x):
#         return self.act(self.bn(self.conv(x)))
#
#     def forward_fuse(self, x):
#         return self.act(self.conv(x))
#
#
# class RepNCSPELAN4_low(nn.Module):
#     # csp-elan
#     def __init__(self, c1, c2, c5=1):  # c5 = repeat
#         super().__init__()
#         c3 = int(c2 / 2)
#         c4 = int(c3 / 2)
#         self.c = c3 // 2
#         self.cv1 = Conv(c1, c3, 1, 1)
#         self.cv3 = nn.Sequential(RepNCSP(c3, c3, c5))
#         self.cv4 = Conv(c3 + (2 * c4), c2, 1, 1)
#
#     def forward(self, x):
#         temp = self.cv1(x)
#         temp3 = self.cv3(temp)
#         y = list(temp.chunk(2, 1))
#         y.append(temp3)
#         temp2 = torch.cat(y, 1)
#         return self.cv4(temp2)
#
#     def forward_split(self, x):
#         y = list(self.cv1(x).split((self.c, self.c), 1))
#         y.extend(m(y[-1]) for m in [self.cv2, self.cv3])
#         return self.cv4(torch.cat(y, 1))
#
#
# class RepNCSPELAN4_high(nn.Module):
#     # csp-elan
#     def __init__(self, c1, c2, c5=1):  # c5 = repeat
#         super().__init__()
#         c3 = c2
#         c4 = int(c3 / 2)
#         self.c = c3 // 2
#         self.cv1 = Conv(c1, c3, 1, 1)
#         self.cv2 = nn.Sequential(RepNCSP(c3 // 2, c4, c5), Conv(c4, c4, 3, 1))
#         self.cv3 = nn.Sequential(RepNCSP(c4, c4, c5), Conv(c4, c4, 3, 1))
#         self.cv4 = Conv(c3 + (2 * c4), c2, 1, 1)
#
#     def forward(self, x):
#         y = list(self.cv1(x).chunk(2, 1))
#         y.extend((m(y[-1])) for m in [self.cv2, self.cv3])
#         return self.cv4(torch.cat(y, 1))
#
#     def forward_split(self, x):
#         y = list(self.cv1(x).split((self.c, self.c), 1))
#         y.extend(m(y[-1]) for m in [self.cv2, self.cv3])
#         return self.cv4(torch.cat(y, 1))
#
#
# if __name__ == "__main__":
#     # Generating Sample image
#     image_size = (1, 24, 224, 224)
#     image = torch.rand(*image_size)
#
#     # Model
#     mobilenet_v1 = RepNCSPELAN4_low(24, 24)
#
#     out = mobilenet_v1(image)
#     print(out.size())

import torch
import torch.nn as nn
import numpy as np
import math
import torch.nn.functional as F

__all__ = ['RepNCSPELAN4_low', 'RepNCSPELAN4_high']


class RepConvN(nn.Module):
    """RepConv is a basic rep-style block, including training and deploy status
    This code is based on https://github.com/DingXiaoH/RepVGG/blob/main/repvgg.py
    """
    default_act = nn.SiLU()  # default activation

    def __init__(self, c1, c2, k=3, s=1, p=1, g=1, d=1, act=True, bn=False, deploy=False):
        super().__init__()
        assert k == 3 and p == 1
        self.g = g
        self.c1 = c1
        self.c2 = c2
        self.act = self.default_act if act is True else act if isinstance(act, nn.Module) else nn.Identity()

        self.bn = None
        self.conv1 = Conv(c1, c2, k, s, p=p, g=g, act=False)
        self.conv2 = Conv(c1, c2, 1, s, p=(p - k // 2), g=g, act=False)

    def forward_fuse(self, x):
        """Forward process"""
        return self.act(self.conv(x))

    def forward(self, x):
        """Forward process"""
        id_out = 0 if self.bn is None else self.bn(x)
        return self.act(self.conv1(x) + self.conv2(x) + id_out)

    def get_equivalent_kernel_bias(self):
        kernel3x3, bias3x3 = self._fuse_bn_tensor(self.conv1)
        kernel1x1, bias1x1 = self._fuse_bn_tensor(self.conv2)
        kernelid, biasid = self._fuse_bn_tensor(self.bn)
        return kernel3x3 + self._pad_1x1_to_3x3_tensor(kernel1x1) + kernelid, bias3x3 + bias1x1 + biasid

    def _avg_to_3x3_tensor(self, avgp):
        channels = self.c1
        groups = self.g
        kernel_size = avgp.kernel_size
        input_dim = channels // groups
        k = torch.zeros((channels, input_dim, kernel_size, kernel_size))
        k[np.arange(channels), np.tile(np.arange(input_dim), groups), :, :] = 1.0 / kernel_size ** 2
        return k

    def _pad_1x1_to_3x3_tensor(self, kernel1x1):
        if kernel1x1 is None:
            return 0
        else:
            return torch.nn.functional.pad(kernel1x1, [1, 1, 1, 1])

    def _fuse_bn_tensor(self, branch):
        if branch is None:
            return 0, 0
        if isinstance(branch, Conv):
            kernel = branch.conv.weight
            running_mean = branch.bn.running_mean
            running_var = branch.bn.running_var
            gamma = branch.bn.weight
            beta = branch.bn.bias
            eps = branch.bn.eps
        elif isinstance(branch, nn.BatchNorm2d):
            if not hasattr(self, 'id_tensor'):
                input_dim = self.c1 // self.g
                kernel_value = np.zeros((self.c1, input_dim, 3, 3), dtype=np.float32)
                for i in range(self.c1):
                    kernel_value[i, i % input_dim, 1, 1] = 1
                self.id_tensor = torch.from_numpy(kernel_value).to(branch.weight.device)
            kernel = self.id_tensor
            running_mean = branch.running_mean
            running_var = branch.running_var
            gamma = branch.weight
            beta = branch.bias
            eps = branch.eps
        std = (running_var + eps).sqrt()
        t = (gamma / std).reshape(-1, 1, 1, 1)
        return kernel * t, beta - running_mean * gamma / std

    def fuse_convs(self):
        if hasattr(self, 'conv'):
            return
        kernel, bias = self.get_equivalent_kernel_bias()
        self.conv = nn.Conv2d(in_channels=self.conv1.conv.in_channels,
                              out_channels=self.conv1.conv.out_channels,
                              kernel_size=self.conv1.conv.kernel_size,
                              stride=self.conv1.conv.stride,
                              padding=self.conv1.conv.padding,
                              dilation=self.conv1.conv.dilation,
                              groups=self.conv1.conv.groups,
                              bias=True).requires_grad_(False)
        self.conv.weight.data = kernel
        self.conv.bias.data = bias
        for para in self.parameters():
            para.detach_()
        self.__delattr__('conv1')
        self.__delattr__('conv2')
        if hasattr(self, 'nm'):
            self.__delattr__('nm')
        if hasattr(self, 'bn'):
            self.__delattr__('bn')
        if hasattr(self, 'id_tensor'):
            self.__delattr__('id_tensor')


class RepNBottleneck(nn.Module):
    # Standard bottleneck
    def __init__(self, c1, c2, shortcut=True, g=1, k=(3, 3), e=0.5):  # ch_in, ch_out, shortcut, kernels, groups, expand
        super().__init__()
        c_ = int(c2 * e)  # hidden channels
        self.cv1 = RepConvN(c1, c_, k[0], 1)
        self.cv2 = Conv(c_, c2, k[1], 1, g=g)
        self.add = shortcut and c1 == c2

    def forward(self, x):
        return x + self.cv2(self.cv1(x)) if self.add else self.cv2(self.cv1(x))


class RepNCSP(nn.Module):
    # CSP Bottleneck with 3 convolutions
    def __init__(self, c1, c2, n=1, shortcut=True, g=1, e=0.5):  # ch_in, ch_out, number, shortcut, groups, expansion
        super().__init__()
        c_ = int(c2 * e)  # hidden channels
        self.cv1 = Conv(c1, c_, 1, 1)
        self.cv2 = Conv(c1, c_, 1, 1)
        self.cv3 = Conv(2 * c_, c2, 1)  # optional act=FReLU(c2)
        self.m = nn.Sequential(*(RepNBottleneck(c_, c_, shortcut, g, e=1.0) for _ in range(n)))

    def forward(self, x):
        return self.cv3(torch.cat((self.m(self.cv1(x)), self.cv2(x)), 1))


def autopad(k, p=None, d=1):  # kernel, padding, dilation
    # Pad to 'same' shape outputs
    if d > 1:
        k = d * (k - 1) + 1 if isinstance(k, int) else [d * (x - 1) + 1 for x in k]  # actual kernel-size
    if p is None:
        p = k // 2 if isinstance(k, int) else [x // 2 for x in k]  # auto-pad
    return p


class Conv(nn.Module):
    # Standard convolution with args(ch_in, ch_out, kernel, stride, padding, groups, dilation, activation)
    default_act = nn.SiLU()  # default activation

    def __init__(self, c1, c2, k=1, s=1, p=None, g=1, d=1, act=True):
        super().__init__()
        self.conv = nn.Conv2d(c1, c2, k, s, autopad(k, p, d), groups=g, dilation=d, bias=False)
        self.bn = nn.BatchNorm2d(c2)
        self.act = self.default_act if act is True else act if isinstance(act, nn.Module) else nn.Identity()

    def forward(self, x):
        return self.act(self.bn(self.conv(x)))

    def forward_fuse(self, x):
        return self.act(self.conv(x))


# -------------------- New: Attention & Gate & GC modules --------------------
class ECA(nn.Module):
    """ECA: Efficient Channel Attention (very lightweight)."""
    def __init__(self, channels, gamma=2, b=1):
        super().__init__()
        t = int(abs((math.log2(max(1, channels)) + b) / gamma))
        k = t if (t % 2) else t + 1
        k = max(3, k)
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.conv = nn.Conv1d(1, 1, kernel_size=k, padding=(k - 1) // 2, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        # x: (B,C,H,W)
        y = self.avg_pool(x)                # (B,C,1,1)
        y = y.squeeze(-1).transpose(-1, -2) # (B,1,C)
        y = self.conv(y)                    # (B,1,C)
        y = self.sigmoid(y).transpose(-1, -2).unsqueeze(-1)  # (B,C,1,1)
        return x * y.expand_as(x)


class DynamicChannelGate(nn.Module):
    """Tiny dynamic gating module that produces per-channel gates from global context."""
    def __init__(self, channels, reduction=8):
        super().__init__()
        mid = max(4, channels // reduction)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Conv2d(channels, mid, 1, bias=True),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, channels, 1, bias=True),
            nn.Sigmoid()
        )

    def forward(self, x):
        w = self.pool(x)
        w = self.fc(w)
        return x * w


class GlobalContextBlock(nn.Module):
    """Lightweight Global Context (GC) block.
    Implementation based on GCNet idea: context modeling + transform + fusion.
    Very lightweight: 1x1 convs + pooling.
    """
    def __init__(self, in_channels, reduction=16):
        super().__init__()
        self.in_channels = in_channels
        self.reduction = reduction
        self.pool = nn.AdaptiveAvgPool2d(1)  # global context
        mid = max(4, in_channels // reduction)
        self.transform = nn.Sequential(
            nn.Conv2d(in_channels, mid, 1, bias=False),
            nn.LayerNorm([mid, 1, 1]) if hasattr(nn, 'LayerNorm') else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, in_channels, 1, bias=False),
            nn.Sigmoid()
        )

    def forward(self, x):
        # x: (B,C,H,W)
        context = self.pool(x)  # (B,C,1,1)
        mask = self.transform(context)  # (B,C,1,1)
        return x * mask


# -------------------- Enhanced classes (same names, with optional enhancements) --------------------
class RepNCSPELAN4_low(nn.Module):
    # csp-elan (enhanced: ECA + DynamicGate + GC optional, default ON)
    def __init__(self, c1, c2, c5=1, use_eca=True, use_gate=True, use_gc=True):
        super().__init__()
        # Original internal computations retained
        c3 = int(c2 / 2)
        c4 = int(c3 / 2)
        self.c = c3 // 2
        self.cv1 = Conv(c1, c3, 1, 1)
        # Keep the original RepNCSP module(s)
        self.cv3 = nn.Sequential(RepNCSP(c3, c3, c5))
        self.cv4 = Conv(c3 + (2 * c4), c2, 1, 1)

        # Enhancement modules (lightweight)
        self.use_eca = use_eca
        self.use_gate = use_gate
        self.use_gc = use_gc

        if self.use_gc:
            # apply GC to the output of the inner path (temp3)
            self.gc = GlobalContextBlock(c3)
        if self.use_eca:
            # apply ECA after concatenation (before cv4) to reweight channels
            self.eca = ECA(c3 + (2 * c4))
        if self.use_gate:
            # dynamic gate applied before final cv4 to modulate channels
            self.gate = DynamicChannelGate(c3 + (2 * c4))

    def forward(self, x):
        # original flow preserved
        temp = self.cv1(x)
        temp3 = self.cv3(temp)  # path through RepNCSP

        # apply global context to temp3 if enabled (improves global semantics)
        if self.use_gc:
            temp3 = self.gc(temp3)

        y = list(temp.chunk(2, 1))  # split original temp into two parts
        y.append(temp3)
        temp2 = torch.cat(y, 1)  # concat exactly as original

        # apply ECA on concatenated tensor (lightweight channel attention)
        if self.use_eca:
            temp2 = self.eca(temp2)

        # apply dynamic gate if enabled
        if self.use_gate:
            temp2 = self.gate(temp2)

        return self.cv4(temp2)

    def forward_split(self, x):
        # keep original split behaviour, but apply enhancements consistently
        y = list(self.cv1(x).split((self.c, self.c), 1))
        # Note: in original file forward_split referenced self.cv2 which wasn't defined for low variant.
        # We keep compatibility by using available modules similarly to forward
        last = y[-1]
        # apply same operations as forward for last branch
        last_m = self.cv3(last)
        if self.use_gc:
            last_m = self.gc(last_m)
        y.append(last_m)
        temp2 = torch.cat(y, 1)
        if self.use_eca:
            temp2 = self.eca(temp2)
        if self.use_gate:
            temp2 = self.gate(temp2)
        return self.cv4(temp2)


class RepNCSPELAN4_high(nn.Module):
    # csp-elan (enhanced: ECA + DynamicGate + GC optional, default ON)
    def __init__(self, c1, c2, c5=1, use_eca=True, use_gate=True, use_gc=True):
        super().__init__()
        # Original internal computations retained
        c3 = c2
        c4 = int(c3 / 2)
        self.c = c3 // 2
        self.cv1 = Conv(c1, c3, 1, 1)
        self.cv2 = nn.Sequential(RepNCSP(c3 // 2, c4, c5), Conv(c4, c4, 3, 1))
        self.cv3 = nn.Sequential(RepNCSP(c4, c4, c5), Conv(c4, c4, 3, 1))
        self.cv4 = Conv(c3 + (2 * c4), c2, 1, 1)

        # Enhancement modules (lightweight)
        self.use_eca = use_eca
        self.use_gate = use_gate
        self.use_gc = use_gc

        if self.use_gc:
            # apply GC to the outputs of cv2/cv3 path (mid-level features)
            # choose a moderate channel size (c4) for GC blocks
            self.gc2 = GlobalContextBlock(c4)
            self.gc3 = GlobalContextBlock(c4)
        if self.use_eca:
            self.eca = ECA(c3 + (2 * c4))
        if self.use_gate:
            self.gate = DynamicChannelGate(c3 + (2 * c4))

    def forward(self, x):
        # original forward preserved
        y = list(self.cv1(x).chunk(2, 1))
        # process branch through cv2/cv3 stacks
        out2 = self.cv2(y[-1])
        out3 = self.cv3(out2)

        # apply GC on these mid outputs if enabled
        if self.use_gc:
            out2 = self.gc2(out2)
            out3 = self.gc3(out3)

        y.extend((out2, out3))
        temp = torch.cat(y, 1)

        # apply ECA and gate before final fusion if enabled
        if self.use_eca:
            temp = self.eca(temp)
        if self.use_gate:
            temp = self.gate(temp)

        return self.cv4(temp)

    def forward_split(self, x):
        # mirror forward but using split
        y = list(self.cv1(x).split((self.c, self.c), 1))
        out2 = self.cv2(y[-1])
        out3 = self.cv3(out2)
        if self.use_gc:
            out2 = self.gc2(out2)
            out3 = self.gc3(out3)
        y.extend((out2, out3))
        temp = torch.cat(y, 1)
        if self.use_eca:
            temp = self.eca(temp)
        if self.use_gate:
            temp = self.gate(temp)
        return self.cv4(temp)


if __name__ == "__main__":
    # Generating Sample image
    image_size = (1, 24, 224, 224)
    image = torch.rand(*image_size)

    # Model - low variant (defaults: use_eca=True, use_gate=True, use_gc=True)
    mobilenet_v1 = RepNCSPELAN4_low(24, 24)

    out = mobilenet_v1(image)
    print("RepNCSPELAN4_low output:", out.size())

    # Model - high variant
    mobilenet_v2 = RepNCSPELAN4_high(24, 24)
    out2 = mobilenet_v2(image)
    print("RepNCSPELAN4_high output:", out2.size())
