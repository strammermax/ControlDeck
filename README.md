# ControlDeck — Homelab Control Center

[![Build, release and deploy](https://github.com/strammermax/ControlDeck/actions/workflows/ci.yml/badge.svg)](https://github.com/strammermax/ControlDeck/actions/workflows/ci.yml)

A lightweight, modular entry point for your homelab, designed for Docker and an unprivileged Debian LXC.

**Current status: infrastructure foundation.** The first release contains a static Next.js/React landing page, a Flask runtime, health checks and build/release/deployment automation. Authentication, providers and the nine functional modules are planned. No infrastructure credentials or privileged operations are exposed by this foundation.

## Documentation

All detailed documentation lives in [`docs/`](docs/README.md).

- [Vision](docs/visie.md)
- [Functional design](docs/functioneel-ontwerp.md)
- [Technical design](docs/technisch-ontwerp.md)
- [Installation: Docker and LXC](docs/INSTALLATION.md)
- [CI/CD and releases](docs/CI-CD.md)
- [Operations and rollback](docs/OPERATIONS.md)
- [Infrastructure](docs/INFRASTRUCTURE.md)
- [Architecture and repository layout](docs/ARCHITECTURE.md)
- [Contributing and third-party code](docs/CONTRIBUTING.md)
- [Security](docs/SECURITY.md)
- [Changelog](docs/CHANGELOG.md)

## Quick start with Docker

```bash
docker compose up --build -d
```

Open `http://127.0.0.1:8080`. Building uses Node.js; the final runtime serves prebuilt files from Python and does not need a Node.js server.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cd frontend
npm ci
npm run build
cd ..
python -m backend.app
```

The development server listens on localhost only. Production uses Gunicorn. Runtime budgets in the design are targets, not measured minimum requirements.

## License

GPL-3.0. See [LICENSE](LICENSE). ProxMenux Monitor is a design and technology reference. No ProxMenux application code has been imported into this foundation; any later reuse must retain applicable notices and comply with its license.
