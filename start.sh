source ./.venv/bin/activate
cd app
uvicorn services.auth.auth_main:app --host 0.0.0.0 --port 8000 --reload
uvicorn services.users.users_main:app --host 0.0.0.0 --port 8001 --reload
uvicorn services.posts.posts_main:app --host 0.0.0.0 --port 8002 --reload