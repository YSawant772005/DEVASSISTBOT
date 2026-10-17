import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

const backendTarget = process.env.VITE_DEV_BACKEND ?? 'http://127.0.0.1:8000'

function parseAllowedHosts(): string[] {
  const raw = process.env.VITE_ALLOWED_HOSTS ?? ''
  const extra = raw
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)

  return ['localhost', '127.0.0.1', '.trycloudflare.com', ...extra]
}

function buildProxy() {
  const backendHttp = backendTarget
  const backendWs = backendTarget.replace(/^http/, 'ws')

  return {
    '/health': {
      target: backendHttp,
      changeOrigin: true,
    },
    '/upload': {
      target: backendHttp,
      changeOrigin: true,
    },
    '/documents': {
      target: backendHttp,
      changeOrigin: true,
    },
    '/ws': {
      target: backendWs,
      ws: true,
      changeOrigin: true,
    },
  }
}

export default defineConfig(() => {
  return {
    plugins: [vue(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      host: '0.0.0.0',
      allowedHosts: parseAllowedHosts(),
      proxy: buildProxy(),
      port: 5173,
      strictPort: true,
    },
    preview: {
      host: '0.0.0.0',
      port: 4173,
      strictPort: true,
      allowedHosts: parseAllowedHosts(),
      proxy: buildProxy(),
    },
    test: {
      environment: 'jsdom',
      globals: true,
      include: ['tests/**/*.spec.ts'],
      restoreMocks: true,
    },
  }
})
