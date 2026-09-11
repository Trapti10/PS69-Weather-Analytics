import type { ReactNode } from 'react'

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-[var(--radius-md)] bg-primary/15 text-lg font-bold text-primary">
            W
          </div>
          <h1 className="text-lg font-semibold text-foreground">Weather Intelligence Platform</h1>
          <p className="text-sm text-muted">National weather event reporting &amp; verification</p>
        </div>
        {children}
      </div>
    </div>
  )
}
