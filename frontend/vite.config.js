import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  resolve: {
    dedupe: ["react", "react-dom", "three"],
  },

  optimizeDeps: {
    include: [
      "react",
      "react-dom",
      "react-dom/client",
      "react/jsx-dev-runtime",
      "three",
      "@react-three/fiber",
      "@react-three/drei",
      "recharts",
      "lucide-react",
    ],
  },

  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
});