# Ghostfolio Agent Frontend

React frontend for the Ghostfolio Agent - an AI-powered portfolio assistant.

## Tech Stack

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling

## Development

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

## Structure

```
src/
├── api/           # API client and types
├── components/    # Reusable UI components
│   └── layout/    # Navigation, Layout
├── contexts/      # React contexts (auth, mode)
├── pages/         # Page components
│   ├── AgentWorkspace.tsx    # Main chat interface
│   ├── ObservabilityCost.tsx # Usage metrics
│   └── VerificationEvals.tsx # Eval runner
└── main.tsx       # Entry point
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API URL (default: `/api`) |

## Docker

The frontend is containerized with nginx for production:

```bash
docker build -t ghostfolio-agent-frontend .
docker run -p 3000:80 ghostfolio-agent-frontend
```
