import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Saat pengembangan (npm run dev), permintaan /api diteruskan ke FastAPI di
// porta 8000, sehingga tidak ada persoalan lintas asal. Setelah `npm run build`,
// FastAPI menyajikan hasil build-nya sendiri dan proxy ini tidak terpakai.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
