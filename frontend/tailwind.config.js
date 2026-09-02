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
        // Stitch Primary Palette (Forest Green)
        primary: {
          DEFAULT: "#004430",
          hover: "#003324",
          container: "#125d44",
          fixed: "#abf1d0",
          "fixed-dim": "#8fd5b5",
          "on-container": "#8ed4b4",
          "on-fixed": "#002115",
        },
        // Stitch Surface & Backgrounds
        surface: {
          DEFAULT: "#f8f9ff",
          dim: "#cbdbf5",
          bright: "#f8f9ff",
          container: "#e5eeff",
          "container-low": "#eff4ff",
          "container-lowest": "#ffffff",
          "container-high": "#dce9ff",
          "container-highest": "#d3e4fe",
          variant: "#d3e4fe",
          tint: "#246a50",
          inverse: "#213145",
          "inverse-on": "#eaf1ff",
        },
        background: "#f8f9ff",
        "on-background": "#0b1c30",
        "on-surface": "#0b1c30",
        "on-surface-variant": "#3f4944",

        // Stitch Secondary Palette
        secondary: {
          DEFAULT: "#58605f",
          container: "#d9e1df",
          fixed: "#dce4e2",
          "fixed-dim": "#c0c8c6",
          "on-container": "#5c6463",
        },

        // Stitch Tertiary Palette
        tertiary: {
          DEFAULT: "#383c3c",
          container: "#4f5353",
          fixed: "#e0e3e2",
          "fixed-dim": "#c4c7c6",
        },

        // Stitch Error & Risk Palette
        error: {
          DEFAULT: "#ba1a1a",
          container: "#ffdad6",
          "on-container": "#93000a",
        },

        // Stitch Success & Verification Palette
        success: {
          DEFAULT: "#00513a",
          container: "#abf1d0",
          "on-container": "#002115",
        },

        // Warning & Caution
        warning: {
          DEFAULT: "#b45309",
          container: "#fef3c7",
          "on-container": "#78350f",
        },

        // Stitch Outline & Borders
        outline: {
          DEFAULT: "#707973",
          variant: "#bfc9c2",
        },
      },
      fontFamily: {
        sans: ['"Hanken Grotesk"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
        hanken: ['"Hanken Grotesk"', "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "8px",
        sm: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
        "2xl": "16px",
        "3xl": "24px",
      },
      boxShadow: {
        subtle: "0 1px 3px rgba(11, 28, 48, 0.05), 0 1px 2px rgba(11, 28, 48, 0.03)",
        card: "0 2px 8px -2px rgba(11, 28, 48, 0.06), 0 1px 4px -1px rgba(11, 28, 48, 0.04)",
        elevated: "0 10px 25px -5px rgba(11, 28, 48, 0.08), 0 8px 10px -6px rgba(11, 28, 48, 0.04)",
      },
    },
  },
  plugins: [],
};
