import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

function readPyprojectVersion(): string {
  const isProdBuild = process.argv.includes('build')
  const pyprojectPath = resolve(__dirname, '..', 'pyproject.toml')
  try {
    const pyproject = readFileSync(pyprojectPath, 'utf-8')
    const m = pyproject.match(/^\s*version\s*=\s*"([^"]+)"/m)
    if (!m) {
      const msg = `[vite] pyproject.toml at ${pyprojectPath} has no version field`
      if (isProdBuild) throw new Error(msg)
      console.warn(`${msg} — falling back to 0.0.0`)
      return '0.0.0'
    }
    return m[1]
  } catch (err) {
    const msg = `[vite] could not read ${pyprojectPath}: ${(err as Error).message}`
    if (isProdBuild) throw new Error(msg)
    console.warn(`${msg} — falling back to 0.0.0`)
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
