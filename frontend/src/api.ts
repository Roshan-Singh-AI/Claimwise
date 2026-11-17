export type User = { user_id: string; email: string; full_name: string; role: string; title?: string; department?: string }
export type Claim = {
  claim_id: string; intake: Record<string, any>; final_outcome: string; internal_status: string;
  preliminary_outcome?: string; risk_assessment?: Record<string, any>; actuarial_breakdown?: Record<string, any>;
  node_traces?: Array<Record<string, any>>; matched_clauses?: Array<Record<string, any>>;
  customer_email_subject?: string; customer_email_body?: string; audit_hash?: string; requires_hitl?: boolean;
  hitl_reason?: string; timestamp?: string;
}
const API = ''
export function getToken() { return localStorage.getItem('claimwise_token') || '' }
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`)
  return data as T
}
export const api = {
  login: (email: string, password: string) => request<{access_token:string; user:User}>('/api/v1/auth/login', { method:'POST', body:JSON.stringify({email,password}) }),
  claims: () => request<{count:number; claims:Claim[]}>('/api/v1/claims'),
  claim: (id:string) => request<Claim>(`/api/v1/claims/${encodeURIComponent(id)}`),
  submit: (payload:Record<string,any>) => request<Claim>('/api/v1/claims/submit', {method:'POST',body:JSON.stringify(payload)}),
  decide: (id:string, payload:Record<string,any>) => request<Claim>(`/api/v1/claims/${encodeURIComponent(id)}/hitl-decision`, {method:'POST',body:JSON.stringify(payload)}),
  policies: () => request<{policies:Record<string,any>[]}>('/api/v1/policies'),
  clauses: (id:string,q='') => request<{policy_id:string;clauses:Record<string,any>[]}>('/api/v1/policies/'+encodeURIComponent(id)+'/clauses?q='+encodeURIComponent(q)),
  audit: () => request<{verification:Record<string,any>;events:Record<string,any>[]}>('/api/v1/audit'),
  health: () => request<Record<string,any>>('/api/v1/health'),
  evals: () => request<Record<string,any>>('/api/v1/evals/run',{method:'POST'}),
}
