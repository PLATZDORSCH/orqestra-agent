/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional: must match `api.auth_token` / ORQESTRA_API_TOKEN on the gateway */
  readonly VITE_ORQESTRA_API_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** Injected at build time by `vite.config.ts` from `pyproject.toml`. */
declare const __APP_VERSION__: string;
