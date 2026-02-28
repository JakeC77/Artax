// src/theme/ThemeModeProvider.tsx
import { type ReactNode, createContext, useContext, useMemo, useState } from 'react'
import { ThemeProvider } from '@mui/material/styles'
import { CssBaseline } from '@mui/material'
import { lightTheme, darkTheme } from '../theme'

type Mode = 'light' | 'dark'

type ThemeModeContextValue = {
  mode: Mode
  setMode: (mode: Mode) => void
  toggleMode: () => void
}

const ThemeModeContext = createContext<ThemeModeContextValue | undefined>(undefined)

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>(() => {
    const stored = localStorage.getItem('app:color-mode') as Mode | null
    return stored === 'dark' || stored === 'light' ? stored : 'light'
  })

  const setMode = (next: Mode) => {
    setModeState(next)
    localStorage.setItem('app:color-mode', next)
  }

  const toggleMode = () => setMode(mode === 'light' ? 'dark' : 'light')

  const theme = useMemo(
    () => (mode === 'light' ? lightTheme : darkTheme),
    [mode],
  )

  const value = useMemo(
    () => ({ mode, setMode, toggleMode }),
    [mode],
  )

  return (
    <ThemeModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  )
}

export function useThemeMode() {
  const ctx = useContext(ThemeModeContext)
  if (!ctx) {
    throw new Error('useThemeMode must be used within ThemeModeProvider')
  }
  return ctx
}

