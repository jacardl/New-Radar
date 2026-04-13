/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      colors: {
        primary: {
          DEFAULT: "#005cb8",
          container: "#1275e2",
        },
        secondary: {
          DEFAULT: "#bb0016",
        },
        surface: {
          containerLowest: "#ffffff",
          containerLow: "#f7f7f7",
          container: "#f0f0f0",
          containerHigh: "#e6e6e6",
          dim: "#dadada",
        },
        onSurface: {
          DEFAULT: "#1a1c1c",
          variant: "#414753",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "var(--background)",
        foreground: "var(--foreground)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}