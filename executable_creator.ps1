$ScriptName = "main.py"         
$VenvDir = "venv"               
$RequirementsFile = "requirements.txt" 

$pythonPath = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    exit 1
}

python -m venv $VenvDir

if (-not (Test-Path "$VenvDir\Scripts\activate")) {
    exit 1
}

& ".\$VenvDir\Scripts\python.exe" -m pip install -r $RequirementsFile

& ".\$VenvDir\Scripts\python.exe" -m pip install pyinstaller

& ".\$VenvDir\Scripts\pyinstaller.exe" --onefile --noconsole $ScriptName
