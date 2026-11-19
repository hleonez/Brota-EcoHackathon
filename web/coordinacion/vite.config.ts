import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Puerto 3000: el origen que la API permite por CORS en desarrollo.
export default defineConfig({
  plugins: [react()],
  server: { port: 3000, strictPort: true },
  preview: { port: 3000, strictPort: true },
});
