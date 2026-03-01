# API Versioning Strategy

## Current Version: v1

All API endpoints are prefixed with `/v1`. This document describes the versioning and deprecation policy.

## Version Format

- **URL prefix**: `/v1`, `/v2`, etc.
- **Header**: `X-API-Version: 1` (injected by the server on all responses)
- **OpenAPI**: `info.version` reflects the application version; path prefix indicates API version

## Deprecation Policy

1. **Minimum 6 months notice** before removing a deprecated version
2. **Deprecation header**: `X-API-Deprecation: true` and `Sunset: <RFC 7231 date>` on deprecated endpoints
3. **Changelog**: Breaking changes documented in [CHANGELOG.md](../CHANGELOG.md)
4. **Migration guides**: Provided for major version upgrades

## Version Lifecycle

| Phase       | Duration | Headers                                      |
|------------|----------|----------------------------------------------|
| Current    | —        | `X-API-Version: 1`                           |
| Deprecated | ≥6 months| `X-API-Deprecation: true`, `Sunset: <date>`   |
| Removed    | —        | 410 Gone                                     |

## Adding a New Version

1. Create `app/api/v2/` with new routers
2. Include v2 router in main app: `app.include_router(v2_router)`
3. Update this document
4. Announce deprecation of v1 with Sunset date

## Client Recommendations

- **Pin to version**: Use `/v1` explicitly; do not rely on unversioned paths
- **Check headers**: Respect `X-API-Deprecation` and `Sunset` for migration planning
- **Idempotency**: Use `Idempotency-Key` on state-changing requests for safe retries
