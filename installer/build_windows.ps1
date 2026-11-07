# Builds the packaged Windows app into dist\TrafficAnalysis\ (run from the project root, inside the .venv).
#   .venv\Scripts\pip install pyinstaller imageio-ffmpeg
#   powershell -File installer\build_windows.ps1
$ErrorActionPreference = "Stop"
if (-not (Test-Path yolov8n.pt)) { .venv\Scripts\python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" }
.venv\Scripts\python -m PyInstaller --noconfirm --clean --name TrafficAnalysis --onedir --console `
  --add-data "yolov8n.pt;." --add-data "app/static;app/static" `
  --collect-all ultralytics --collect-all torchvision --collect-all imageio_ffmpeg --collect-submodules uvicorn `
  --hidden-import python_multipart --hidden-import multipart --hidden-import lap `
  --exclude-module tensorboard --exclude-module pytest --exclude-module polars `
  run_app.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path dist\TrafficAnalysis\TrafficAnalysis.exe)) { throw "PyInstaller build FAILED" }
Write-Host "Built: dist\TrafficAnalysis\TrafficAnalysis.exe"
