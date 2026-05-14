# Runbook: CODEOWNERS maintenance

> How to edit `CODEOWNERS` without breaking everyone's MRs.

## How GitLab reads CODEOWNERS

- **Last matching line wins** per file.
- **Sections** (`^[Section name]`) require at least one approval from
  the listed owners.
- **Wildcard patterns** are evaluated top-to-bottom; the last match
  determines the owners.

## When to edit CODEOWNERS

| Situation | Edit |
|---|---|
| New team onboarding | Add `/apps/<team>-*/   @cdo/<team>-team` |
| Person leaving a team | Remove them from the team's GitLab group, NOT from CODEOWNERS |
| Project moves between teams | Update the wildcard for the project's prefix |
| New cross-cutting requirement | Add a Section (e.g. `^[Restricted-data-cleared]`) |

## When NOT to edit CODEOWNERS

- **Adding an individual person to a project.** Put them in the team's
  GitLab group instead.
- **Granting one-off access.** That's not what CODEOWNERS is for.
- **As a workaround for a missing CI rule.** Fix the CI rule.

## Editing safely

1. **Always work on a feature branch**, never on `main` directly.
2. **Run the linter locally**:

   ```bash
   python tools/scripts/check_ownership_sync.py
   ```

   It verifies every wildcard has a matching GitLab group, every
   section has owners, and no path is left without an owner.

3. **Open an MR**. The MR requires `@cdo/platform-team` approval
   (CODEOWNERS itself is owned by platform-team — see line 1 of the
   file).

4. **Don't merge late on Friday.** A bad CODEOWNERS rule blocks
   everyone's MRs until rolled back.

## Common patterns

A new team:

```
# Per-team app rules
/apps/finance-*/   @cdo/finance-team
/libs/finance-*/   @cdo/finance-team
```

A cross-cutting reviewer required (e.g. anything touching `.gitlab-ci.yml`):

```
/.gitlab-ci.yml    @cdo/platform-team @cdo/security
/.gitlab/          @cdo/platform-team @cdo/security
```

A section that requires a separate approval (in addition to per-path
rules):

```
^[Restricted-data-cleared]
/apps/*/contracts/*restricted*.yaml   @cdo/restricted-cleared
/libs/common-masks/                   @cdo/restricted-cleared @cdo/data-governance
```

## How CODEOWNERS interacts with the MR template

The MR template checks include `Restricted columns touched`. If checked,
GitLab automatically adds the `^[Restricted-data-cleared]` section's
approvers as required reviewers — so checking the box is meaningful,
don't lie.

## Checklist

- [ ] Feature branch named `feature/codeowners-…`
- [ ] `check_ownership_sync.py` passes locally
- [ ] MR has `@cdo/platform-team` approval
- [ ] Merged on a weekday, not late Friday

## See also

- `access-control.md` — adjacent topic, but covers data access, not
  review approval
