import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Deployed to https://canadafoodsupply.kushankbajaj.com via GitHub Pages with a CNAME,
// so the site sits at the domain root and base stays '/'. If this ever moves to a project
// path (kushankb.github.io/canada-food-twin/), change base here AND drop public/CNAME —
// every data fetch already goes through import.meta.env.BASE_URL, so nothing else changes.
export default defineConfig({
  base: '/',
  plugins: [react(), tailwindcss()],
  build: { outDir: 'dist', assetsInlineLimit: 0 },
  // Honour a PORT assigned by the harness; Vite does not read it on its own.
  server: { port: Number(process.env.PORT) || 5173 },
})
