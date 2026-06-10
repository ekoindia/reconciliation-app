import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,   // bind to 0.0.0.0 so other machines on the network can connect
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true }
    }
  }
})
