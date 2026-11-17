from __future__ import annotations
import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from app import main
from app.database import ClaimDatabase, SEED_SCENARIOS


class TestClaimwiseHttpFlow(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
        handle.close()
        self.path = handle.name
        self.db = ClaimDatabase(self.path)
        self.original_db = main.db
        main.db = self.db
        self.client = TestClient(main.app)

    def tearDown(self):
        main.db = self.original_db
        if os.path.exists(self.path):
            os.unlink(self.path)

    def token(self, email, password):
        response = self.client.post('/api/v1/auth/login', json={'email': email, 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['access_token']

    def test_login_claim_visibility_and_role_gates(self):
        self.assertEqual(self.client.get('/api/v1/claims').status_code, 401)
        policyholder = self.token('asha.rao@example.in', 'Policy@2026')
        ph_headers = {'Authorization': f'Bearer {policyholder}'}
        claims = self.client.get('/api/v1/claims', headers=ph_headers)
        self.assertEqual(claims.status_code, 200, claims.text)
        self.assertTrue(all(c['intake']['claimant_email'] == 'asha.rao@example.in' for c in claims.json()['claims']))
        self.assertEqual(self.client.get('/api/v1/claims/CLM-2026-803', headers=ph_headers).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/audit', headers=ph_headers).status_code, 403)
        policies = self.client.get('/api/v1/policies', headers=ph_headers)
        self.assertEqual(policies.status_code, 200)
        self.assertTrue(all(p['holder_email'] == 'asha.rao@example.in' for p in policies.json()['policies']))
        foreign_claim = dict(SEED_SCENARIOS[2])
        foreign_claim['claimant_email'] = 'asha.rao@example.in'
        self.assertEqual(self.client.post('/api/v1/claims/submit', json=foreign_claim, headers=ph_headers).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/claims/CLM-2026-804/hitl-decision', json={'officer_name':'Asha Rao','action':'APPROVE','officer_notes':'test'}, headers=ph_headers).status_code, 403)

        officer = self.token('roshan@claimwise.demo', 'DemoOfficer@2026')
        off_headers = {'Authorization': f'Bearer {officer}'}
        self.assertEqual(self.client.get('/api/v1/audit', headers=off_headers).status_code, 200)
        self.assertEqual(self.client.get('/api/v1/claims', headers=off_headers).json()['count'], 6)

    def test_http_claim_submission_and_review(self):
        officer = self.token('roshan@claimwise.demo', 'DemoOfficer@2026')
        headers = {'Authorization': f'Bearer {officer}'}
        payload = dict(SEED_SCENARIOS[0])
        payload['claim_id'] = 'CLM-HTTP-TEST-01'
        submitted = self.client.post('/api/v1/claims/submit', json=payload, headers=headers)
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()['claim_id'], 'CLM-HTTP-TEST-01')
        fetched = self.client.get('/api/v1/claims/CLM-HTTP-TEST-01', headers=headers)
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()['final_outcome'], 'APPROVED')
        audit = self.client.get('/api/v1/audit', headers=headers)
        self.assertEqual(audit.status_code, 200)
        self.assertTrue(audit.json()['verification']['valid'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
