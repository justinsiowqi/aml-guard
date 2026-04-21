import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#fafafa",
        surface: "#ffffff",
        "surface-alt": "#f5f5f5",
        border: "#e5e5e5",
        text: {
          DEFAULT: "#171717",
          muted: "#737373",
        },
        primary: "#1e40af",
        danger: "#991b1b",
        success: "#166534",
        warning: "#92400e",
        accent: "#FFDD00",
      },
      fontFamily: {
        display: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Display"',
          '"SF Pro Text"',
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        body: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"SF Pro Text"',
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          '"SF Mono"',
          "Menlo",
          "Consolas",
          '"Liberation Mono"',
          "monospace",
        ],
      },
      maxWidth: {
        canvas: "80rem",
      },
    },
  },
  plugins: [],
};

export default config;
