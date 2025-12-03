# OpenAPI TypeScript Client Generation Guide

This project uses **@hey-api/openapi-ts** to automatically generate TypeScript clients from the FastAPI backend's OpenAPI schema.

## Why Use Generated Clients?

✅ **Type Safety** - Backend and frontend types stay in sync automatically
✅ **No Manual Updates** - Changes to backend API are reflected immediately
✅ **Prevents Bugs** - Eliminates type mismatches (like the 18 we just fixed)
✅ **Better DX** - Autocomplete and intellisense for all API endpoints

---

## Setup

### 1. Install Dependencies

```bash
npm install
```

This installs:
- `@hey-api/openapi-ts` (dev) - Code generator
- `@hey-api/client-axios` (prod) - Runtime client

### 2. Ensure Backend is Running

The generator needs to fetch the OpenAPI schema:

```bash
# Make sure backend is accessible at:
http://localhost:8000/openapi.json
```

### 3. Generate the Client

```bash
npm run generate:api
```

This creates `src/generated/` with:
- `types.ts` - All TypeScript types from backend models
- `services.ts` - Type-safe API service methods
- `client.ts` - Axios client configuration

---

## Usage

### Basic API Call

```typescript
import { DefaultService } from '@/generated';

// Old way (manual):
const response = await api.getDocuments();

// New way (generated):
const response = await DefaultService.getDocuments();
// ✅ Fully typed response
// ✅ Autocomplete for all methods
// ✅ Compile-time errors if API changes
```

### With React Hooks

Create custom hooks that use the generated client:

```typescript
// src/hooks/useDocuments.ts
import { useQuery } from '@tanstack/react-query';
import { DocumentsService } from '@/generated';

export function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: () => DocumentsService.getDocuments(),
  });
}
```

### Configure Client

```typescript
import { OpenAPI } from '@/generated';

// Set base URL
OpenAPI.BASE = 'http://localhost:8000';

// Set auth token
OpenAPI.TOKEN = 'your-jwt-token';
```

---

## Migration Strategy

### Phase 1: Parallel Usage (Current)
Keep old `api.ts` working while migrating pages one by one.

```typescript
// OLD: src/lib/api.ts (keep for now)
import api from '@/lib/api';

// NEW: src/generated (use for new code)
import { DocumentsService } from '@/generated';
```

### Phase 2: Migrate One Page
Pick a simple page (e.g., Documents) and convert it:

```typescript
// Before:
const data = await api.getDocuments();

// After:
const data = await DocumentsService.getDocuments();
```

### Phase 3: Replace Gradually
- Migrate high-traffic pages first
- Delete old methods from `api.ts` as you go
- Eventually delete `api.ts` entirely

---

## Configuration

### openapi-ts.config.ts

```typescript
export default defineConfig({
  client: '@hey-api/client-axios',    // Use axios (we already have it)
  input: 'http://localhost:8000/openapi.json',  // Backend OpenAPI schema
  output: {
    path: './src/generated',          // Where to generate files
    format: 'prettier',               // Auto-format generated code
    lint: 'eslint',                   // Auto-lint generated code
  },
  types: {
    enums: 'javascript',              // Generate JS enums (better tree-shaking)
    dates: 'types+transform',         // Handle date serialization
  },
  services: {
    asClass: true,                    // Generate service classes
  },
});
```

---

## Workflow

### Daily Development

1. **Backend changes** → Update FastAPI models/routes
2. **Regenerate client** → Run `npm run generate:api`
3. **TypeScript errors** → Shows you what broke
4. **Fix frontend** → Update code to match new types

### CI/CD Integration

Add to your build pipeline:

```bash
# Before building frontend:
npm run generate:api
npm run build
```

This ensures frontend always uses latest backend schema.

---

## Troubleshooting

### "Cannot connect to localhost:8000"

**Solution:** Make sure backend is running:
```bash
docker-compose up backend
```

### "Generated files have errors"

**Solution:** Check backend OpenAPI schema is valid:
```bash
curl http://localhost:8000/openapi.json | jq
```

### "Types don't match"

**Solution:** Regenerate after backend changes:
```bash
npm run generate:api
```

---

## Benefits We Get

### Before (Manual api.ts)
- ❌ 18 type mismatches we just fixed
- ❌ `KnowledgeBase.id: number` when it's actually `string`
- ❌ Missing `knowledge_base_id` in responses
- ❌ Manual updates for every backend change

### After (Generated Client)
- ✅ Types always match backend
- ✅ Compile errors prevent runtime bugs
- ✅ Zero manual maintenance
- ✅ Refactoring is safe (TypeScript catches everything)

---

## Next Steps

1. ✅ Setup complete (you are here)
2. ⏳ Run `npm install` to install dependencies
3. ⏳ Run `npm run generate:api` to generate first client
4. ⏳ Migrate Documents page to use generated client
5. ⏳ Create React Query hooks
6. ⏳ Migrate remaining pages
7. ⏳ Delete old `api.ts`

---

## Resources

- [@hey-api/openapi-ts docs](https://heyapi.vercel.app/)
- [FastAPI OpenAPI docs](https://fastapi.tiangolo.com/advanced/extending-openapi/)
- [React Query integration](https://tanstack.com/query/latest/docs/framework/react/overview)
