import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/upload': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/validate': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/submit': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/corpus': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/models': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/training': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    }
  }
})