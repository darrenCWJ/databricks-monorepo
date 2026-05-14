## What does this change?

_One paragraph._

## Change ticket

`PROJ-XXXX` _(mandatory for SOC2 — link to Jira)_

## Risk + rollback

- Risk level: low / medium / high
- Rollback plan: _how to revert if this misbehaves_

## Data classification touchpoints

- [ ] No Restricted columns touched
- [ ] Touches Restricted columns — `@cdo/data-governance` and
  `@cdo/restricted-cleared` approval required

## Checklist

- [ ] Lint passes (`just lint`)
- [ ] Tests pass (`just test`)
- [ ] Bundle validates (`just bundle-validate`)
- [ ] AGENTS.md updated if behaviour changed
- [ ] `docs/data-architecture.md` row added/updated if project changed shape
