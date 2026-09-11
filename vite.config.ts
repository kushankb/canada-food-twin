import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  // Expose PUBLIC_* to import.meta.env. A missing Mapbox token then shows as a message on the
  // map instead of failing the build, which is what $env/static/public would do.
  envPrefix: ['VITE_', 'PUBLIC_'],
  // Honour a PORT assigned by the harness; Vite does not read it on its own.
  server: { port: Number(process.env.PORT) || 5173 },
});
