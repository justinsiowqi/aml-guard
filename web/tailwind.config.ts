import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#f8f9fa",
        surface: "#f8f9fa",
        "surface-dim": "#d9dadb",
        "surface-bright": "#f8f9fa",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f3f4f5",
        "surface-container": "#edeeef",
        "surface-container-high": "#e7e8e9",
        "surface-container-highest": "#e1e3e4",
        "surface-variant": "#e1e3e4",
        "on-surface": "#191c1d",
        "on-surface-variant": "#444653",
        "inverse-surface": "#2e3132",
        "inverse-on-surface": "#f0f1f2",
        outline: "#757684",
        "outline-variant": "#c4c5d5",

        primary: "#00288e",
        "on-primary": "#ffffff",
        "primary-container": "#1e40af",
        "on-primary-container": "#a8b8ff",
        "primary-fixed": "#dde1ff",
        "primary-fixed-dim": "#b8c4ff",
        "on-primary-fixed": "#001453",
        "on-primary-fixed-variant": "#173bab",
        "inverse-primary": "#b8c4ff",

        secondary: "#785a00",
        "on-secondary": "#ffffff",
        "secondary-container": "#fdc425",
        "on-secondary-container": "#6d5200",
        "secondary-fixed": "#ffdf9a",
        "secondary-fixed-dim": "#f7be1d",
        "on-secondary-fixed": "#251a00",
        "on-secondary-fixed-variant": "#5a4300",

        tertiary: "#611e00",
        "on-tertiary": "#ffffff",
        "tertiary-container": "#872d00",
        "on-tertiary-container": "#ffa583",
        "tertiary-fixed": "#ffdbce",
        "tertiary-fixed-dim": "#ffb59a",
        "on-tertiary-fixed": "#380d00",
        "on-tertiary-fixed-variant": "#802a00",

        error: "#ba1a1a",
        "on-error": "#ffffff",
        "error-container": "#ffdad6",
        "on-error-container": "#93000a",

        accent: "#fdc425",
      },
      fontFamily: {
        sans: ['Inter', '"SF Pro Text"', '"Segoe UI"', "Roboto", '"Helvetica Neue"', "Arial", "sans-serif"],
        display: ['Inter', '"SF Pro Display"', '"Segoe UI"', "Roboto", "sans-serif"],
        body: ['Inter', '"SF Pro Text"', '"Segoe UI"', "Roboto", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
        serif: ['"Source Serif Pro"', 'Georgia', '"Times New Roman"', "serif"],
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        full: "0.75rem",
      },
    },
  },
  plugins: [],
};

export default config;
