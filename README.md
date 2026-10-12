# Video Localizer Final

## Environment
```powershell
$env:GEMINI_API_KEYS="media1,media2"
$env:GEMINI_TRANSLATE_KEYS="trans1,trans2"
$env:GEMINI_API_RPM="2"
$env:GEMINI_CLI_RPM="2"
$env:RATE_WINDOW_SECONDS="65"
$env:RATE_COOLDOWN_SECONDS="65"
```
Translation calls Gemini CLI with a selected key injected as `GEMINI_API_KEY`. If no media key or translation key is ready, `/api/process` rejects the job before upload.

## Run
```powershell
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python -m uvicorn app.main:app --reload
```

## Limiter dimension
The local limiter is keyed by `(credential slot, model)`. The same key can therefore have separate rolling counters for the STT model and TTS model. Translation keys have a separate counter for `gemma-4-31b-it`. Note that Google documents Gemini API quotas as project-level rather than API-key-level, while limits vary by model. This local implementation is deliberately conservative and useful for scheduling, but multiple keys from one project do not create additional provider quota.
