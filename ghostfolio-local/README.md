# Run Ghostfolio locally

Use this to run a local Ghostfolio instance so you can create an access token for the Ghostfolio Agent.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose.

## Steps

1. **Create `.env`** (one-time):

   ```bash
   cd ghostfolio-local
   copy .env.example .env
   ```

   (On macOS/Linux: `cp .env.example .env`)

2. **Start Ghostfolio:**

   ```bash
   docker compose up -d
   ```

3. **Open the app:** http://localhost:3333

4. **Create an account** (register with any email/password; no email verification in local setup).

5. **Get your access token:**
   - Go to **Settings** (gear icon) → **Security**.
   - Under **Access tokens**, create a new token and copy it.

6. **Use the token in the agent:** Put it in your project `.env` as:
   ```env
   GHOSTFOLIO_API_URL=http://localhost:3333
   GHOSTFOLIO_ACCESS_TOKEN=<paste your token here>
   ```

## Stop

```bash
docker compose down
```

To remove data as well: `docker compose down -v`
