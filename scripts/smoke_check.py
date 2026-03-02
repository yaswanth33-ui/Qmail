import qmail.api as api
import time
print('klen=', len(api._derive_email_key('u','a@x','b@x','s')))
print('revoked_before=', api._is_token_revoked('faketoken'))
api._revoke_token('faketoken', ttl_seconds=1)
print('revoked_after=', api._is_token_revoked('faketoken'))
time.sleep(1.1)
print('revoked_expired=', api._is_token_revoked('faketoken'))
