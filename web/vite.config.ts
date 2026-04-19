import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

function readPyprojectVersion(): string {
  try {
    const pyproject = readFileSync(resolve(__dirname, '..', 'pyproject.toml'), 'utf-8')
    const m = pyproject.match(/^\s*version\s*=\s*"([^"]+)"/m)
    return m?.[1] ?? '0.0.0'
  } catch {
    return '0.0.0'
  }
}

const APP_VERSION = readPyprojectVersion()

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(APP_VERSION),
  },
  build: {
    outDir: 'dist',
  },
  server: {
    port: 4201,
    proxy: {
      '/api': {
        target: 'http://localhost:4200',
        changeOrigin: true,
      },
    },
  },
})
