import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],

    server: {
        host: "0.0.0.0",

        allowedHosts: [
            "unfortunately-pirates-viewers-gel.trycloudflare.com",
            "memphis-fresh-thermal-donation.trycloudflare.com",
            "approaches-differences-standard-cod.trycloudflare.com"
        ]
    }
})