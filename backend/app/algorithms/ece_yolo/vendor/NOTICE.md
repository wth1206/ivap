# Third-party ECE-YOLO modules

These files are **verbatim copies** of the ECE-YOLO custom modules used to train
`best.pt`. They are kept here so the project is self-contained and does not
depend on an external training checkout at runtime.

| File | SHA-256 (prefix) | Source |
|---|---|---|
| `ESPMStem.py` | `6999D8572340…` | `D:\yolo11（2）\ultralytics-main\ultralytics\nn\Addmodules\ESPMStem.py` |
| `RepNCSPELAN4.py` | `91C28DAA6C47…` | `...\Addmodules\RepNCSPELAN4.py` |
| `DynamicHead.py` | `F716062AE323…` | `...\Addmodules\DynamicHead.py` |

Copied on 2026-11-06. No source edits were made.

## License / attribution

The source checkout is an Ultralytics 8.3.209 derivative and carries the
**AGPL-3.0** license. `DynamicHead` also derives from the YOLOv8 dynamic-head
implementation attributed in its header. Keep this notice and the upstream
license when redistributing the project.

## Runtime notes

- `ESPMStem.py` imports `ultralytics.nn.modules.conv.Conv`.
- `RepNCSPELAN4.py` is self-contained (torch/numpy only).
- `DynamicHead.py` imports `mmcv.ops.ModulatedDeformConv2d` at module import.
  This machine does not have mmcv; the P3 loader installs a compatibility shim
  backed by `torchvision.ops.deform_conv2d` **before** importing this file.
- Do not import `DynamicHead` directly from this package without the shim.

See `docs/03-ece-yolo-integration-notes.md` for the validation record.
