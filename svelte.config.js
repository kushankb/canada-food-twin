import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ pages: 'build', assets: 'build', fallback: '404.html' }),
    // Served at the root of canadafoodsupply.kushankbajaj.com via static/CNAME. If this ever
    // moves to a project path, set base here and drop the CNAME — every fetch goes through
    // $app/paths, so nothing else changes.
    paths: { base: '' },
  },
};

export default config;
