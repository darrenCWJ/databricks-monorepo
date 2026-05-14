# Runbook: cleared-group intake

> Onboarding a new team that needs Restricted-data access.

## What's a cleared group

A GitLab group whose members are pre-cleared by HR + Security to handle
Restricted-classified data. The group is SCIM-synced to Databricks,
which uses it to govern catalog access via column masks and row filters.

## The flow

1. **Business need stated** — leadership decides Team X needs access
   to dataset Y. Recorded in a Jira ticket in `GOV-`.

2. **Security review** — `@cdo/security` reviews the use case, the
   business justification, and the scope of access. Decision recorded
   on the Jira ticket.

3. **HR clearance** — every named member of Team X is cleared by HR
   (employment status, NDA, IM8 awareness training complete).

4. **Platform team creates the group** — `@cdo/platform-team` opens
   an MR to `infra/terraform-databricks/groups.tf`:

   ```hcl
   resource "databricks_group" "team_x_cleared" {
     display_name = "cdo-team-x-cleared"
   }
   ```

   Plus a CODEOWNERS section in `CODEOWNERS`:

   ```
   /apps/team-x-*/   @cdo/team-x-team
   /libs/team-x-*/   @cdo/team-x-team
   ```

5. **Group memberships** — managed in GitLab UI by the platform team.
   The GitLab group becomes the source of truth; SCIM pushes the
   members into the Databricks group within ~15 minutes.

6. **Access grants** — once the group exists, dataset-specific grants
   (column masks, row filters) flow through the
   `runbooks/access-control.md` "Granting a team access to a Restricted
   column" path.

7. **Member onboarding** — each member completes:
   - IM8 Tier 1 awareness training (annual).
   - PDPA handling training (one-time).
   - This monorepo's `AGENTS.md` + the team's `apps/AGENTS.md`.

8. **Quarterly review** — the team's lead re-certifies the membership
   list every quarter. Members who haven't logged in for 90 days are
   removed.

## What to put in the Jira ticket

- Business need (1 paragraph).
- Dataset(s) the team needs access to.
- Classification of those datasets.
- Expected duration (permanent / 6 months / project-bound).
- Team lead's HR-approved sign-off.

## Common reasons we say no

- **Access requested but dataset is Confidential.** Different governance
  path; see compliance team.
- **No clear scope.** "Access to all of finance data" is not a scope.
- **Existing group could cover this.** Don't proliferate groups.

## Checklist

- [ ] Jira `GOV-` ticket opened
- [ ] Security signed off
- [ ] HR clearance per member confirmed
- [ ] Terraform MR merged (creates the group)
- [ ] CODEOWNERS MR merged (claims the project prefix)
- [ ] First members added in GitLab → SCIM synced
- [ ] Required training completed by all members

## See also

- `access-control.md` — what you do AFTER the group exists
- `codeowners-maintenance.md` — adding the CODEOWNERS rules
