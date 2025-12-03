import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  client: '@hey-api/client-axios',
  input: 'http://localhost:8000/openapi.json',
  output: {
    path: './src/generated',
    format: 'prettier',
    lint: 'eslint',
  },
  types: {
    enums: 'javascript',
    dates: 'types+transform',
  },
  services: {
    asClass: true,
  },
});
