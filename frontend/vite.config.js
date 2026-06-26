import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Dev API proxy target. Defaults to :8000 (committed default — unchanged).
  // Override locally (e.g. when :8000 is taken by another app) by setting
  // VITE_API_TARGET in a gitignored frontend/.env.local, e.g.
  //   VITE_API_TARGET=http://localhost:8001
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const apiTarget = env.VITE_API_TARGET || 'http://localhost:8000'
  return {
    // Production build is served under /recon behind nginx (http://host/recon/);
    // Vite rewrites every asset URL to sit under it and the React Router basename
    // in main.jsx is derived from the same value, so routing stays in lockstep.
    // Local `npm run dev` stays at root so direct :3000 access is unaffected.
    base: mode === 'production' ? '/recon/' : '/',
    plugins: [react()],
    server: {
      port: 3000,
      host: true,   // bind to 0.0.0.0 so other machines on the network can connect
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true }
      }
    }
  }
})
