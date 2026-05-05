# Run Streamlit using the project venv only (avoids Roaming Python / experimental NumPy on PATH).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
& "$PSScriptRoot\venv\Scripts\python.exe" -m streamlit run bwa_frontend.py
