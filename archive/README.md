# IVAP 源码归档

此目录用于存放交接/备份用 zip 包，zip 不提交 GitHub。

生成：

```powershell
.\.venv\Scripts\python.exe scripts\archive_project.py
# 不包含 best.pt
.\.venv\Scripts\python.exe scripts\archive_project.py --no-weights
```

生成物：

```text
archive/IVAP-source-YYYYMMDD.zip
archive/IVAP-source-YYYYMMDD-manifest.txt
archive/IVAP-source-YYYYMMDD.sha256.txt
```

排除：`.env`、`.env.docker`、`.venv`、`.mysql`、`node_modules`、`dist`、上传图片、运行日志、FAISS 运行时索引、MySQL 数据。

说明：默认包含 `best.pt`，便于私有交接；上传 GitHub 时仍按 `.gitignore` 排除权重。
