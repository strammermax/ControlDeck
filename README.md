# ControlDeck — Homelab Control Center

[![Build, release and deploy](https://github.com/strammermax/ControlDeck/actions/workflows/ci.yml/badge.svg)](https://github.com/strammermax/ControlDeck/actions/workflows/ci.yml)

A lightweight, modular entry point for your homelab, designed for Docker and an unprivileged Debian LXC.

**Current status: configurable dashboard shell with Google login.** Menu, modules and providers come from split JSON files. Authorized administrators manage user profiles; users have their own persistent theme and last-page preferences. Google OAuth credentials and an approved administrator are required to sign in. Provider API adapters and dashboard widget rendering are planned.

## Documentation

All detailed documentation lives in [`docs/`](docs/README.md).

The maintainer's deployment is available at [controldeck.vanburik.info](https://controldeck.vanburik.info).

- [Vision](docs/visie.md)
- [Functional design](docs/functioneel-ontwerp.md)
- [Technical design](docs/technisch-ontwerp.md)
- [Interface and navigation](docs/UI.md)
- [JSON configuration and providers](docs/CONFIGURATION.md)
- [Login, users and preferences](docs/AUTHENTICATION.md)
- [Installation: Docker and LXC](docs/INSTALLATION.md)
- [CI/CD and releases](docs/CI-CD.md)
- [Operations and rollback](docs/OPERATIONS.md)
- [Infrastructure](docs/INFRASTRUCTURE.md)
- [HTTPS and tunnel routing](docs/HTTPS.md)
- [Architecture and repository layout](docs/ARCHITECTURE.md)
- [Contributing and third-party code](docs/CONTRIBUTING.md)
- [Security](docs/SECURITY.md)
- [Changelog](docs/CHANGELOG.md)

## Quick start with Docker

```bash
docker compose up --build -d
```

Configure the Google OAuth environment and account list as described in [Authentication](docs/AUTHENTICATION.md), and use an HTTPS reverse proxy. An unconfigured installation stays closed to visitors. Building uses Node.js; the final runtime serves prebuilt files from Python and does not need a Node.js server.

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

## Termix

De optionele Terminal-integratie gebruikt een afzonderlijke Docker-container, de bestaande Google-login en een beveiligde Nginx-gateway. Zie [Termix-installatie en beheer](docs/TERMIX.md).
