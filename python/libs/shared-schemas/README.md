# Shared Schemas

Shared Pydantic schemas for API contracts across steven-universe services.

**Path**: `python/libs/shared-schemas/`

## Purpose

This package provides type-safe API contracts that replace the role of `.proto` files in gRPC:
- **Single source of truth** for request/response models
- **Runtime validation** via Pydantic
- **Type safety** across Python services
- **OpenAPI generation** for documentation

## Package Structure

```
python/libs/shared-schemas/
├── pyproject.toml              # Package definition
├── shared_schemas/
│   ├── __init__.py
│   ├── common.py              # Generic response wrappers (SuccessResponse)
│   └── file_service.py        # File service API contracts
└── README.md
```