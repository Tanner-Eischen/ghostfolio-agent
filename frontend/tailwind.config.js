/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Primary accent color
        primary: "#13c8ec",
        "primary-hover": "#0ea5c6",
        "primary-dim": "rgba(19, 200, 236, 0.1)",

        // Background colors
        "background-light": "#f6f8f8",
        "background-dark": "#101f22",

        // Surface colors
        "surface-dark": "#162a2e",
        "surface-darker": "#0d191b",

        // Border colors
        "border-dark": "#234248",
        "surface-border": "#234248",

        // Text colors
        "text-dim": "#92c0c9",
        "text-secondary": "#92c0c9",
      },
      fontFamily: {
        display: ["Inter", "sans-serif"],
        sans: ["Inter", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.5rem",
        xl: "0.75rem",
        "2xl": "1rem",
        full: "9999px",
      },
    },
  },
  plugins: [],
}
