# 示例数据

用于不接触真实业务数据时复现检测、报告和 RAG 演示。

| 文件 | 用途 |
|---|---|
| `visdrone-sample.jpg` | VisDrone 无人机航拍验证图，用于 `/detection/predict` |
| `knowledge/visdrone.txt` | VisDrone 10 类说明 |
| `knowledge/ece_yolo.docx` | ECE-YOLO 结构说明 |
| `knowledge/visdrone_overview.pdf` | VisDrone 数据集概述（2 页） |

这些文件来自项目开发期公开资料与验证图，仅用于本地演示；请勿当作真实业务数据或模型精度证明。

上传示例：

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/detection/predict" -F "file=@samples\visdrone-sample.jpg"
curl.exe -X POST "http://127.0.0.1:8000/api/v1/knowledge/upload" -F "file=@samples\knowledge\visdrone.txt"
```
