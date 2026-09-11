import { describe, expect, it } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { ThemeProvider } from '@/app/providers/ThemeProvider'
import { useTheme } from '@/hooks/useTheme'
import { render } from '@testing-library/react'

function ThemeProbe() {
  const { theme, toggleTheme } = useTheme()
  return (
    <div>
      <span data-testid="theme-value">{theme}</span>
      <button onClick={toggleTheme}>Toggle</button>
    </div>
  )
}

describe('ThemeProvider', () => {
  it('defaults to dark theme', () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    )
    expect(screen.getByTestId('theme-value')).toHaveTextContent('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('toggles to light and back, persisting to localStorage', () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    )

    fireEvent.click(screen.getByText('Toggle'))
    expect(screen.getByTestId('theme-value')).toHaveTextContent('light')
    expect(localStorage.getItem('ps69_theme')).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')

    fireEvent.click(screen.getByText('Toggle'))
    expect(screen.getByTestId('theme-value')).toHaveTextContent('dark')
    expect(localStorage.getItem('ps69_theme')).toBe('dark')
  })

  it('reads a persisted preference on mount', () => {
    localStorage.setItem('ps69_theme', 'light')
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    )
    expect(screen.getByTestId('theme-value')).toHaveTextContent('light')
  })
})
