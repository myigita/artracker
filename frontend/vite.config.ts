import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Anything the app requests under /api gets forwarded to the FastAPI
      // dev server. Keeps frontend calls same-origin ("/api/trackers/"), so
      // no CORS setup is needed, and it mirrors production — where FastAPI
      // serves the built app and there's only one origin anyway.
      '/api': 'http://localhost:8000',
    },
  },
})
