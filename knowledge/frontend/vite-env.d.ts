/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AZURE_TENANT_ID: string
  readonly VITE_AZURE_CLIENT_ID: string
  readonly VITE_AZURE_AUTHORITY: string
  readonly VITE_AZURE_REDIRECT_URI?: string
  readonly VITE_AZURE_SCOPES: string
  readonly VITE_GRAPHQL_URL?: string
  readonly VITE_TENANT_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

