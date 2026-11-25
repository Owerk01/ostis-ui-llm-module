import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Обычная сборка — dev-стенд; `--mode lib` — React-панель;
// `--mode transport` — самостоятельный пакет логики без React.
export default defineConfig(({ mode }) => ({
  plugins: mode === 'transport' ? [] : [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
  build:
    mode === 'transport'
      ? {
          outDir: 'dist-transport',
          emptyOutDir: true,
          cssCodeSplit: false,
          lib: {
            entry: 'src/transport/index.ts',
            formats: ['es'],
            fileName: 'index',
          },
          rollupOptions: {
            external: ['ts-sc-client'],
          },
        }
      : mode === 'lib'
        ? {
            outDir: 'dist-lib',
            emptyOutDir: true,
            cssCodeSplit: false,
            lib: {
              entry: 'src/index.ts',
              formats: ['es'],
              fileName: 'index',
            },
            rollupOptions: {
              external: ['react', 'react-dom', 'react/jsx-runtime', 'ts-sc-client'],
            },
          }
        : {
            outDir: 'dist',
            sourcemap: true,
          },
}))
