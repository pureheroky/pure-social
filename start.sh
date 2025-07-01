source ./.venv/bin/activate
cd app
uvicorn services.auth.src.auth.main:app --reload
