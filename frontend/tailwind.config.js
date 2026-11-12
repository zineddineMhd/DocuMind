/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "Segoe UI", "Roboto", "sans-serif"] },
      colors: {
        brand: {
          50: "#f3f0ff", 100: "#e9e3ff", 200: "#d4c9ff", 300: "#b5a1ff", 400: "#9171fb",
          500: "#7350f2", 600: "#5b3fd6", 700: "#4a31b3", 800: "#3b2a8c", 900: "#2a1f66",
        },
        ink: { 900: "#16132d", 700: "#3a3657", 500: "#6b6785", 300: "#b4b1c7" },
      },
      boxShadow: { card: "0 1px 2px rgba(22,19,45,.04), 0 4px 16px rgba(22,19,45,.05)" },
    },
  },
  plugins: [],
};
