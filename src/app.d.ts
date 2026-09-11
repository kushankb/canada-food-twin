// See https://svelte.dev/docs/kit/types#app.d.ts
declare global {
  namespace App {}
  interface ImportMetaEnv {
    /** Mapbox public token. Read via import.meta.env so a missing token is a runtime
     *  message on the map, not a failed build. */
    readonly PUBLIC_MAPBOX_TOKEN?: string
  }
}

export {}
