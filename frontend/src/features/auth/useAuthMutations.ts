import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { login as loginRequest, register as registerRequest } from '@/services/api/auth'
import type { LoginPayload, RegisterPayload } from '@/services/api/auth'
import { useAuth } from '@/hooks/useAuth'
import { normalizeApiError } from '@/services/api/client'
import { homePathForRole } from '@/utils/roleHome'

export function useLoginMutation() {
  const { login } = useAuth()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: (payload: LoginPayload) => loginRequest(payload),
    onSuccess: (data, variables) => {
      login({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        userId: data.user_id,
        email: variables.email,
        role: data.role,
      })
      navigate(homePathForRole(data.role), { replace: true })
    },
  })
}

export function useRegisterMutation() {
  const { login } = useAuth()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: (payload: RegisterPayload) => registerRequest(payload),
    onSuccess: (data, variables) => {
      login({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        userId: data.user_id,
        email: variables.email,
        role: data.role,
      })
      navigate(homePathForRole(data.role), { replace: true })
    },
  })
}

export { normalizeApiError }
