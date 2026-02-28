import { createTheme, alpha } from '@mui/material/styles'
import type { ThemeOptions, PaletteMode } from '@mui/material'
import type {} from '@mui/x-data-grid/themeAugmentation'

declare module '@mui/material/styles' {
  interface Palette {
    custom: {
      lightBackground: string
    }
  }

  interface PaletteOptions {
    custom?: {
      lightBackground?: string
    }
  }
}

const titleFont = 'TiemposHeadline, Georgia, serif'
const sansSerifRegularFont = 'HaasGrotTextTrial-Regular, Inter, system-ui, -apple-system, sans-serif'
const sansSerifMediumFont = 'HaasGrotTextTrial-Medium, Inter, system-ui, -apple-system, sans-serif'

// 🎨 Brand colors
const colors = {
  white: '#FFFFFF',
  black: '#141414',
  charcoal: '#1C1C1C',
  ivory: '#F4F0E6',
  softWhite: '#FEFDFB',
  gold: '#C6A664',
  emerald: '#0F5C4C',
  grayLight: '#D6D6D6',
  grayMedium: '#5E5E5E',
  grayDark: '#2B2B2B',
}

// Generates the theme depending on the mode (light/dark)
const getDesignTokens = (mode: PaletteMode): ThemeOptions => ({
  palette: {
    mode,
    primary: {
      main: colors.emerald,
      light: alpha(colors.emerald, 0.8),
      dark: '#0A3C32',
      contrastText: colors.white,
    },
    secondary: {
      main: colors.gold,
      light: alpha(colors.gold, 0.85),
      dark: '#9B7F3F',
      contrastText: colors.black,
    },
    custom: {
      lightBackground: mode === 'light' ? colors.softWhite : colors.black,
    },
    ...(mode === 'light'
      ? {
          // 🌞 LIGHT THEME
          background: {
            default: colors.white, // main background
            paper: colors.ivory,  // surfaces: cards, modals, etc.
          },
          text: {
            primary: colors.charcoal,
            secondary: colors.grayMedium,
            disabled: colors.grayLight,
          },
          divider: colors.grayLight,
        }
      : {
          // 🌚 DARK THEME
          background: {
            default: colors.charcoal, // main background
            paper: colors.black,      // surfaces: cards, modals, etc.
          },
          text: {
            primary: colors.ivory,
            secondary: colors.grayLight,
            disabled: alpha(colors.grayLight, 0.5),
          },
          divider: colors.grayDark,
        }),
    // Actions using emerald with opacity
    action: {
      hover: alpha(colors.emerald, 0.2),    // emerald 20%
      selected: alpha(colors.emerald, 0.3), // emerald 30%
      disabled: alpha(colors.grayMedium, 0.3),
      disabledBackground: alpha(colors.grayMedium, 0.1),
    },
  },

  // Typography configuration: bodyFont for general text, titleFont for headings
  typography: {
    fontFamily: sansSerifRegularFont,
    body1: {
      fontFamily: sansSerifRegularFont,
    },
    body2: {
      fontFamily: sansSerifMediumFont,
    },
    button: {
      fontFamily: sansSerifMediumFont,
      textTransform: 'none',
    },
    h1: {
      fontFamily: titleFont,
      fontWeight: 600,
    },
    h2: {
      fontFamily: titleFont,
      fontWeight: 600,
    },
    h3: {
      fontFamily: titleFont,
      fontWeight: 600,
    },
    h4: {
      fontFamily: titleFont,
      fontWeight: 600,
    },
    h5: {
      fontFamily: titleFont,
      fontWeight: 600,
    },
    h6: {
      fontFamily: titleFont,
      fontWeight: 600,
    },
  },

  shape: {
    borderRadius: 8,
  },
  components: {
    MuiToolbar: {
      styleOverrides: {
        root: {
          // Slightly taller toolbar to better match the visual design
          minHeight: 50,
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: {
          minHeight: 0, // overall tabs bar height
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          minHeight: 0,          // override MUI default 48px
          padding: '4px 12px',   // tighter vertical & horizontal padding
          minWidth: 'auto',      // override MUI default 160px
          '@media (min-width:600px)': {
            minWidth: 'auto',    // also override the responsive minWidth
          },
        },
      },
    },
    MuiMenu: {
      styleOverrides: {
        paper: {
          backgroundColor: mode === 'light' ? colors.white : colors.charcoal,
          backgroundImage: 'none',
        },
      },
    },
    MuiPaper: {
      defaultProps: {
        elevation: 0, // no shadow by default
      },
      styleOverrides: {
        root: {
          borderRadius: 0.5,
          backgroundImage: 'none', // remove default background image in some variants
        },
        outlined: {
          borderColor: 'divider', // use theme divider color for outlined papers
        },
      },
    },
    MuiButtonBase: {
      styleOverrides: {
        root: {
          '&:focus-visible': {
            outline: 'none',
          },
        },
      },
    },
    MuiCssBaseline: {
      styleOverrides: {
        '*, *::before, *::after': {
          outline: 'none',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 4, // 0.5 * 8 (el default borderRadius base es 8)
        },
      },
    },
    MuiDataGrid: {
      styleOverrides: {
        root: {
          '& .MuiDataGrid-cell': {
            display: 'flex',
            alignItems: 'center',
          },
        },
      },
    },
  },  
})

// Export ready-to-use themes
export const lightTheme = createTheme(getDesignTokens('light'))
export const darkTheme = createTheme(getDesignTokens('dark'))
