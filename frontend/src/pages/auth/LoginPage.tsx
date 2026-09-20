import { useState, type FormEvent } from 'react'
import axios from 'axios'
import { Link } from 'react-router-dom'
import { AuthLayout } from '@/layouts/AuthLayout'
import { Card, CardBody } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Field'
import { Button } from '@/components/ui/Button'
import { useLoginMutation } from '@/features/auth/useAuthMutations'
import { normalizeApiError } from '@/services/api/client'
import { LOGIN_ROLE_LABEL } from '@/constants/status'
import type { ApiErrorBody, UserRole } from '@/types/domain'

const LOGIN_ROLE_OPTIONS: UserRole[] = ['CITIZEN', 'ANALYST', 'ADMIN']

function getLoginErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error) && typeof error.response?.data?.detail === 'string') {
    return error.response.data.detail
  }
  return normalizeApiError(error).message
}

export function LoginPage() {
  const [role, setRole] = useState<UserRole>('CITIZEN')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const mutation = useLoginMutation()

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    mutation.mutate({ email, password, role })
  }

  const errorMessage = mutation.isError ? getLoginErrorMessage(mutation.error) : null

  return (
    <AuthLayout>
      <Card>
        <CardBody>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
            <Field label="Login as" htmlFor="role" required hint="Select the account type you're using to sign in.">
              <Select id="role" required value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
                {LOGIN_ROLE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {LOGIN_ROLE_LABEL[option]}
                  </option>
                ))}
              </Select>
            </Field>
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

            {errorMessage && (
              <p role="alert" className="text-sm text-danger">
                {errorMessage}
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
