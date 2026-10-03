// Light / dark theme: "system" follows the OS; the choice is remembered per browser.

export type ThemeChoice = 'system' | 'dark' | 'light'
export const THEME_ORDER: ThemeChoice[] = ['system', 'dark', 'light']
const KEY = 'bb-theme'
const media = window.matchMedia('(prefers-color-scheme: dark)')

export function loadTheme(): ThemeChoice {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'dark' || saved === 'light' || saved === 'system') return saved
  } catch {
    // storage blocked: fall back to system
  }
  return 'system'
}

export function applyTheme(choice: ThemeChoice): void {
  const dark = choice === 'dark' || (choice === 'system' && media.matches)
  document.documentElement.classList.toggle('dark', dark)
  try {
    localStorage.setItem(KEY, choice)
  } catch {
    // storage blocked: the choice just isn't remembered
  }
}

export function onSystemThemeChange(listener: () => void): () => void {
  media.addEventListener('change', listener)
  return () => media.removeEventListener('change', listener)
}
