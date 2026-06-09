# Security Policy

Fanbook is designed for private team deployment. It is not hardened as a
public multi-tenant SaaS application.

## Supported Versions

Security fixes are handled on the default branch until versioned releases are
introduced.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to the repository owner or
maintainer. Do not open a public issue containing:

- API keys, provider credentials, database passwords, session cookies, or
  bootstrap administrator credentials.
- Uploaded EPUB contents, exported artifacts, database dumps, or runtime
  storage files.
- Reproduction steps that expose a live private deployment.

Include a clear description, affected commit or version, impact, and safe
reproduction steps using mock data whenever possible.

## Deployment Notes

- Use strong values for all variables in `backend/.env.example` before running
  `backend/docker-compose.yml`.
- Rotate `FANBOOK_BOOTSTRAP_ADMIN_PASSWORD` after the first administrator is
  created, then remove it from the deployment environment when practical.
- Keep `SPRING_PROFILES_ACTIVE=prod` for private deployment. The production
  profile disables OpenAPI and Swagger UI by default and limits Actuator
  exposure to health.
- Terminate TLS and apply network access controls at the reverse proxy or
  hosting layer.
- Treat MySQL data and `FANBOOK_STORAGE_ROOT` as one backup unit.
