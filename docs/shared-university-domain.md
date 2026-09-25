# US-10: one SDU domain for Student and Staff

SDU gives students and staff addresses on the same domain, `sdu.edu.kz`, so the
domain cannot tell the two roles apart. A domain may now appear in both
`UNIVERSITY_STUDENT_DOMAINS` and `UNIVERSITY_STAFF_DOMAINS`. Before this change,
a domain in both lists stopped the server from starting.

- **Domain in both lists (SDU):** the email code proves that the address is SDU's,
  and the role the user chose in **Verify your role** is granted.
- **Domain in one list:** it also proves the role, as in US-07. This setup is
  still supported and tested.

Configuration for SDU:
```
UNIVERSITY_STUDENT_DOMAINS=sdu.edu.kz
UNIVERSITY_STAFF_DOMAINS=sdu.edu.kz
```

## How the role is carried

- `POST /api/profile/verification/start/` stores the requested role in the
  session, next to the pending code. A new request replaces both.
- `confirm` grants exactly that role, after re-checking that the address's domain
  may prove it. A code with no requested role in the session (for example, after
  signing in elsewhere) is refused with "Request a new code first."
- The verification state includes `pending_role`. The dialog shows the code step
  only for the role the code was sent for; the other role starts at the email step.

## Trade-off

With one domain, a student can verify as **Staff**: the email proves SDU
membership, not the role. Telling them apart would need another signal, such as
a rule on the part before `@` (for example, student-ID digits for students) or
confirmation by an administrator. Neither is implemented.

`university.affiliation_for_domain()` returns `None` for a shared domain, so a
future Google Workspace (`hd`) path cannot pick a role from it on its own.

## Verification

All 123 backend tests pass. `SharedUniversityDomainTests` covers:
- either role verified with the same domain;
- the latest request deciding the role;
- a code with no requested role refused;
- other domains refused;
- the shared-domain mapping.

Headless Chrome with console mail checked:
- `.local/verify-shared-domain.mjs`: a `sdu.edu.kz` address verified as Student,
  then as Staff; the second dialog started at the email step; a Gmail address was
  refused.
- `.local/verify-roles.mjs`: the separate-domain setup still passes.
