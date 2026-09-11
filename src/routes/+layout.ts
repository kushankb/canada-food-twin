// Static site. ssr is off because mapbox-gl and deck.gl need a browser; prerender still
// emits the shell so GitHub Pages serves index.html at the root.
export const prerender = true;
export const ssr = false;
