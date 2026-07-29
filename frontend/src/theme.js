/**
 * Shared design tokens — matches the personal-portfolio design system this
 * demo is styled to sit alongside. Single source of truth for both the
 * password gate and the main app.
 */

export const COLORS = {
  bg:             "#EFF3F1",
  ink:            "#20281F", // sentiments: warm charcoal, not pure black
  inkMuted:       "#5B655D",
  inkFaint:       "#8A9089",

  primary:        "#3F6659", // AI-suggested scores, primary actions, links
  primaryTint:    "#DCE8E3",
  primaryDark:    "#2E4C42",

  amber:          "#C9A24A", // human-overridden scores
  amberTint:      "#F5EBD3",

  terracotta:     "#C97C4C", // warnings / verification flags / errors
  terracottaTint: "#F7E4D6",

  blue:           "#4A7A9E", // informational (waking up, rate-limit notice)
  blueTint:       "#E1EBF1",

  cardBg:         "#FFFFFF",
  cardBorder:     "#E7E1D6",
};

export const RADIUS = "14px";

export const FONT_STACK =
  "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

export const globalStyleSheet = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  * { box-sizing: border-box; }

  body {
    font-family: ${FONT_STACK};
    font-size: 17px;
    line-height: 1.7;
    color: ${COLORS.ink};
    background: ${COLORS.bg};
  }

  .es-card {
    background: ${COLORS.cardBg};
    border: 1px solid ${COLORS.cardBorder};
    border-radius: ${RADIUS};
    transition: transform 0.18s ease, box-shadow 0.18s ease;
  }
  .es-card--hover:hover {
    transform: translateY(-4px);
    box-shadow: 0 16px 32px rgba(32, 40, 31, 0.10);
  }

  .es-btn {
    font-family: ${FONT_STACK};
    border-radius: ${RADIUS};
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.12s ease, opacity 0.12s ease, box-shadow 0.12s ease;
    border: none;
  }
  .es-btn:hover:not(:disabled) { transform: translateY(-2px); }
  .es-btn:active:not(:disabled) { transform: translateY(0); }
  .es-btn:disabled { cursor: not-allowed; opacity: 0.55; transform: none; }

  .es-btn-primary {
    background: ${COLORS.primary};
    color: #fff;
    box-shadow: 0 4px 12px rgba(63, 102, 89, 0.25);
  }
  .es-btn-primary:hover:not(:disabled) { background: ${COLORS.primaryDark}; }

  .es-btn-ghost {
    background: transparent;
    color: ${COLORS.ink};
    border: 1px solid ${COLORS.cardBorder};
  }
  .es-btn-ghost:hover:not(:disabled) { background: ${COLORS.primaryTint}; border-color: ${COLORS.primary}; }

  .es-btn-dark {
    background: ${COLORS.ink};
    color: #fff;
  }
  .es-btn-dark:hover:not(:disabled) { background: ${COLORS.primaryDark}; }

  .es-input {
    font-family: ${FONT_STACK};
    font-size: 17px;
    border-radius: ${RADIUS};
    border: 1px solid ${COLORS.cardBorder};
    background: #fff;
    color: ${COLORS.ink};
    outline: none;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }
  .es-input:focus {
    border-color: ${COLORS.primary};
    box-shadow: 0 0 0 3px ${COLORS.primaryTint};
  }

  input[type="range"] { accent-color: ${COLORS.primary}; }

  ::selection { background: ${COLORS.primaryTint}; color: ${COLORS.primaryDark}; }

  /* -------------------------------------------------------------------- */
  /* Responsive layout — main app grid collapses to one column on mobile   */
  /* -------------------------------------------------------------------- */

  .es-header-inner {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 16px;
    max-width: 1100px;
    margin: 0 auto;
  }

  .es-main {
    max-width: 1100px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
    gap: 24px;
    padding: 28px 32px 64px;
  }

  @media (max-width: 860px) {
    .es-main { grid-template-columns: 1fr; padding: 20px 16px 48px; gap: 20px; }
    .es-header-inner { align-items: flex-start; }
  }

  @media (max-width: 520px) {
    .es-card { padding: 20px !important; }
  }
`;
