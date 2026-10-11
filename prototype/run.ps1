$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$modelArtifact = Join-Path (Split-Path $PSScriptRoot -Parent) "artifacts\selected_model\pooled_poisson_xgboost.joblib"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Project Python environment not found: $pythonExe"
}

if (-not (Test-Path -LiteralPath $modelArtifact)) {
    & $pythonExe -m prototype.train_models
}

& $pythonExe -m streamlit run (Join-Path $PSScriptRoot "app.py")
