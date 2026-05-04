import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/upload': {
        target: 'https://pkd-declaration.azurewebsites.net',
        changeOrigin: true,
      },
      '/validate': {
        target: 'https://pkd-declaration.azurewebsites.net',
        changeOrigin: true,
      },
      '/submit': {
        target: 'https://pkd-declaration.azurewebsites.net',
        changeOrigin: true,
      },
      '/corpus': {
        target: 'https://pkd-declaration.azurewebsites.net',
        changeOrigin: true,
      },
      '/models': {
        target: 'https://pkd-declaration.azurewebsites.net',
        changeOrigin: true,
      },
      '/training': {
        target: 'https://pkd-declaration.azurewebsites.net',
        changeOrigin: true,
      },
      '/health': {
        target: 'https://pkd-declaration.azurewebsites.net',
        changeOrigin: true,
      },
    }
  }
})