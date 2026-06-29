import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8093'

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      }
    }
  },
  build: {
    target: 'es2020',
    minify: 'esbuild',
    cssCodeSplit: true,
    reportCompressedSize: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/svelte')) {
            return 'vendor-svelte';
          }
        },
      },
    },
  },
})
