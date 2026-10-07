# Push lifecycle regression tests

From `server/`, run `python -m unittest discover -s tests -v`.
The tests use the standard library; no Firebase credentials, database or FCM
delivery are required. Firebase messaging is mocked at its external boundary.

These changes support `med1001/Privora-Mobile#3` (PAR-02). Deploy this backend
before the mobile branch `codex/par-02-push-account-lifecycle`: new mobile builds
require `toUserId` on incoming/cancel data messages. Existing clients can ignore
the additional field. Unregister now checks the authenticated token owner,
without changing the HTTP request format.

Four tests passed locally on 7 October 2026. Device/FCM validation has not run;
the mobile `docs/PAR-02-VALIDATION.md` records the complete acceptance recipe.
