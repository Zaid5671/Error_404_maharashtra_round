import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    // API_PORT lets a second copy run beside the usual one (default 8000)
    proxy: { '/api': { target: `http://localhost:${process.env.API_PORT ?? 8000}`, rewrite: (p) => p.replace(/^\/api/, '') } },
  },
})
