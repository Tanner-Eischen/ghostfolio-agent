# Railway deployment

Ghostfolio Agent runs as two Railway services connected to the same GitHub repository.

| Service | Dockerfile | Health check |
| --- | --- | --- |
| `backend` | `Dockerfile.backend` | `/health` |
| `frontend` | `Dockerfile.frontend` | `/health` |

## Create the backend

1. Create a Railway project from `Tanner-Eischen/ghostfolio-agent`.
2. Name the first service `backend`.
3. Set its Dockerfile path to `Dockerfile.backend`.
4. Set its health-check path to `/health`.
5. Add `OPENAI_API_KEY`, `SECRET_KEY`, and the optional variables you use from `.env.example`.
6. Set `USE_MOCK_DATA=true` unless the service has a Ghostfolio URL and access token.
7. Generate a public domain if you want to use `/docs` or `/health` outside Railway.

## Create the frontend

1. Add a second service from the same repository and name it `frontend`.
2. Set its Dockerfile path to `Dockerfile.frontend`.
3. Set its health-check path to `/health`.
4. Set `BACKEND_URL` to `http://${{backend.RAILWAY_PRIVATE_DOMAIN}}:${{backend.PORT}}`.
5. Generate a public domain for the frontend.

`BACKEND_URL` is substituted into the Nginx configuration when the frontend container starts. A new backend domain therefore does not require a frontend rebuild.

## CORS

Set the backend `CORS_ORIGINS` variable to the frontend public URL. Use a comma-separated list if you have more than one trusted frontend.

## Verify the deployment

1. Open the backend `/health` route. Confirm that it returns `status: healthy`.
2. Open the frontend `/health` route. Confirm that it returns `OK`.
3. Load the frontend and confirm that its health request succeeds.
4. Send one chat request with mock data.
5. Review both service logs for startup errors and failed health checks.

Do not put `OPENAI_API_KEY`, `GHOSTFOLIO_ACCESS_TOKEN`, or `SECRET_KEY` in frontend variables.
