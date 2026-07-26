# FYI.md — open questions blocking items in the current loop

Only currently-open questions live here. Answered ones get removed once
the user confirms and the blocked item re-enters PROPOSE/PLAN.

## Password reset needs email on the account (PROPOSAL.md item 3)

**Blocked on:** Django's stdlib `PasswordResetForm` looks up users by
`email` (`get_users(email)`), but `SignupForm`
(`apps/accounts/views.py`) collects only username + password — "no
email/profile requirements yet," per its own docstring. Building the
stock reset flow as-is would silently match zero users for every
existing and new account.

**What's needed to unblock — pick one:**
1. Add a required `email` field to `SignupForm`/`UserCreationForm`
   (changes the signup form for every future user; existing users would
   still have no email and couldn't use reset until they set one some
   other way).
2. Add an optional `email` field, and gate the "olvidé mi contraseña"
   link/flow on having one set — existing accounts without an email
   still can't self-serve reset.
3. Skip email entirely and reset via a different mechanism instead
   (e.g. an admin-assisted reset, or a security-question flow) — more
   custom code, no email dependency.

Reverted the partial build (URLs/views/templates) rather than ship a
reset flow that doesn't work for anyone. Design is otherwise ready
(Django's stdlib views, same low-effort pattern `SignupView` already
uses) once the email question above is answered.

## Payment gateway live verification (PROPOSAL.md item 5, BACKLOG.csv rows 41/49)

**Blocked on:** real sandbox/test credentials for Stripe (hosted checkout
page round-trip), Bold (webhook spec — their own docs never returned
usable content when checked), PayU/ePayco (amount format), Mercado Pago
(manifest string). None of these can be exercised without actual gateway
accounts — this is an access question, not a code decision.

**What's needed to unblock:** sandbox/test credentials for whichever of
these 4 gateways you want verified next, entered into `PaymentGatewayConfig`
via `/config/` in a real (non-fake-provider) local run.
