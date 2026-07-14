export const designTokens = {
  color: {
    background: "#edf1f7",
    surface: "#ffffff",
    surfaceSoft: "#f7f9fc",
    text: "#162033",
    muted: "#687386",
    primary: "#2563eb",
    primaryStrong: "#1d4ed8",
    cyan: "#0891b2",
    success: "#16a34a",
    warning: "#d97706",
    danger: "#dc2626",
    line: "#dce3ed"
  },
  radius: {
    sm: 6,
    md: 8,
    lg: 10
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24
  },
  typography: {
    title: 20,
    body: 15,
    caption: 12
  }
} as const;

export type DesignTokens = typeof designTokens;
