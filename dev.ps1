$root = $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\backend'; .\.venv\Scripts\Activate.ps1; python -m uvicorn app.main:app --reload"
Start-Process powershell -ArgumentList "-NoExit","-Command","cd '$root\frontend'; npm run dev"
