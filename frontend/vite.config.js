import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('react-select')) return 'select-vendor';
          if (
            id.includes('react-markdown') ||
            id.includes('remark-') ||
            id.includes('micromark') ||
            id.includes('mdast') ||
            id.includes('hast') ||
            id.includes('unified') ||
            id.includes('unist') ||
            id.includes('vfile')
          ) {
            return 'markdown-vendor';
          }
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('scheduler')) {
            return 'react-vendor';
          }
          return 'vendor';
        },
      },
    },
  },
})
