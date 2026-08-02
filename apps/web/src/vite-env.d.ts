interface ImportMetaEnv {
  readonly VITE_DEFAULT_LOCALE?: string;
  readonly VITE_RUNTIME_PROFILE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
