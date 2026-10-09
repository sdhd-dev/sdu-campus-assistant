# US-07: Student and Staff only after verification

Every account starts as **Visitor**. Choosing **Student** or **Staff** in the
profile opens **Verify your role**: enter an SDU email, choose **Send code**,
enter the code, then choose **Verify**. The role changes only when the server
accepts the code, and only if the address matches the role (see
[Student and Staff addresses](#student-and-staff-addresses)). Closing the dialog
leaves the role unchanged.

Other rules:
- A verified role shows a **Verified** badge and can be chosen again at any time
  without a new code.
- **Visitor** is always available and needs no verification.
- **Remove verification** clears the proof and returns the role to Visitor.

This replaces the separate **University status** block from US-06 and reverses
one US-06 rule: verification now sets the role instead of leaving it alone. The
code rules are still those of US-06, now in the shared `accounts/email_codes.py`
module that US-08 also uses.

## Student and Staff addresses

SDU uses `sdu.edu.kz` for students and staff alike, so the domain cannot tell them
apart. The part before `@` does:

| Role | Address | Example |
| --- | --- | --- |
| Student | Student ID, digits only | `220103045@sdu.edu.kz` |
| Staff | `name.surname`, Latin letters, exactly one dot | `aigerim.sadykova@sdu.edu.kz` |

- The domain must still be one of the role's configured domains, so in production
  set `sdu.edu.kz` in both `UNIVERSITY_STUDENT_DOMAINS` and
  `UNIVERSITY_STAFF_DOMAINS`. A domain in both lists no longer stops the server.
- The address is lower-cased before the check, so `Aigerim.Sadykova@SDU.edu.kz`
  is accepted as Staff.
- Both formats live in `LOCAL_PARTS` in `accounts/university.py`.
  `affiliation_for_email()` uses them both when a code is requested and again on
  confirm. The two formats never overlap, so an address proves at most one role.
- Requesting Staff with any other address, such as `220103045@sdu.edu.kz`,
  `aigerimsadykova@…`, `a.k.sadykova@…`, or another domain, returns 400 with
  "Для сотрудника email должен быть в формате имя.фамилия@sdu.edu.kz".
- The dialog runs the same Staff check before sending and shows
  `name.surname@sdu.edu.kz` as the placeholder. The server still decides.
- `affiliation_for_domain()` returns no role for a domain shared by both roles.
  A future Google Workspace path (a verified `hd` claim) therefore cannot pick a
  role from the domain alone.

## Rules enforced by the server

- `PATCH /api/profile/` accepts `STUDENT` or `STAFF` only when the value matches
  `verified_affiliation`. Otherwise it returns 400 with
  `{"profile_type":["Verify your SDU email to choose Student."]}`, or the same
  message for Staff. `VISITOR` is always accepted.
- A database check constraint enforces the same rule. `profile_type` must be
  `VISITOR` or equal a non-null `verified_affiliation`, so neither code nor a
  direct database write can store an unproven role.
- `POST /api/profile/verification/start/` takes exactly `{"email", "role"}`.
  - `role` must be `STUDENT` or `STAFF`.
  - Staff requires `name.surname@` on a staff domain, as described above.
  - A Staff address requested as Student is refused with a message naming the
    right role: "This is a staff address. Choose Staff to verify it."
- `confirm` sets the verified status and `profile_type` in one write.
  `DELETE /api/profile/verification/` clears both and sets `VISITOR`.
- One account has one university address. Verifying the other role replaces the
  first proof, and returning to the first role then needs a new code.
- `GET /api/profile/` also returns `verified_affiliation`, `university_email`, and
  `verification_available`. When no university domains are configured,
  unverified Student and Staff options are disabled.

## Existing accounts

Migration `0005_role_requires_verification` runs before the constraint is added.
It sets every Student or Staff account without matching verification to Visitor.
This cannot be reversed: the previous self-selected role is not kept. Those users
see Visitor and verify when they next choose Student or Staff.

## Verification

All 114 backend tests pass on this branch (`manage.py test accounts core --keepdb`),
including valid Staff, Staff with a student ID, no dot, two dots, another domain,
and a student ID still verifying Student. Headless Chrome through the Vite proxy
(`.local/verify-roles.mjs`, ignored) checked:
- Opening and closing the dialog, including with Escape, leaves Visitor unchanged.
- A student address is refused for Staff with the right message.
- A wrong code, then the right one, sets Student with the badge.
- `PATCH` of an unverified role returns 400.
- Visitor can be chosen and saved, and Student can be chosen again without a
  dialog.
- The role persists after reload.
- The dialog has no horizontal overflow at 320 px.
- Removing verification returns the role to Visitor.

## Manual checklist

1. Sign in with a new account; confirm **Visitor**, and that Student and Staff read
   "Requires your SDU email."
2. Click **Student**; confirm the dialog opens and Visitor stays selected. Press
   Escape; confirm nothing changed.
3. Click **Staff**; confirm the placeholder `name.surname@sdu.edu.kz`. Enter
   `220103045@sdu.edu.kz`; confirm "Для сотрудника email должен быть в формате
   имя.фамилия@sdu.edu.kz" and that no code is sent.
4. Click **Student**, send a code (printed in the Django terminal in development),
   enter a wrong code, then the right one. Confirm **Student** with **Verified**.
5. Choose **Visitor** and save, then **Student** again; confirm no dialog.
6. **Remove verification**; confirm Visitor and no badge.
