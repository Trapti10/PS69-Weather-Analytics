import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AuthLayout } from '@/layouts/AuthLayout'
import { Card, CardBody } from '@/components/ui/Card'
import { Field, Input } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { useLoginMutation } from '@/features/auth/useAuthMutations'
import { normalizeApiError } from '@/services/api/client'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const mutation = useLoginMutation()

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    mutation.mutate({ email, password })
  }

  const error = mutation.isError ? normalizeApiError(mutation.error) : null

  return (
    <AuthLayout>
      <Card>
        <CardBody>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <Field label="Email" htmlFor="email" required>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field label="Password" htmlFor="password" required>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>

            {error && (
              <p role="alert" className="text-sm text-danger">
                {error.message}
              </p>
            )}

            <Button type="submit" isLoading={mutation.isPending} className="mt-1 w-full">
              Log in
            </Button>
          </form>
        </CardBody>
      </Card>
      <p className="mt-4 text-center text-sm text-muted">
        Don't have an account?{' '}
        <Link to="/register" className="font-medium text-primary hover:text-primary-hover">
          Register as a citizen
        </Link>
      </p>
    </AuthLayout>
  )
}
