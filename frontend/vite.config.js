import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],

    server: {
        host: "0.0.0.0",

        allowedHosts: [
            "https://fioricet-participated-told-mainly.trycloudflare.com",
            "gaps-johnson-turner-responsibility.trycloudflare.com",
            "idaho-downloads-compound-owned.trycloudflare.com",
            "barbara-samples-mild-urge.trycloudflare.com",
            "excess-circular-valentine-fifth.trycloudflare.com",
            "pushed-exotic-involves-pointing.trycloudflare.com",
            "theorem-bright-louisiana-stay.trycloudflare.com"
        ]
    }
})