# libs/ — agent rules

> Extends the root AGENTS.md.

## Libraries must not depend on apps

A library may not `import` from any `apps/<name>/`. If you find yourself
wanting to, the code probably belongs in another lib (or stays in the app).

## Stricter quality bar

- Test coverage ≥ 90% on every lib (apps target 70%).
- Every public function has a docstring + type annotations.
- Breaking changes require a major version bump and a deprecation cycle.

## When to remove a library

If only one app still uses a library, move the code back into that app
and delete the lib. Carrying unused libs adds review and CI cost forever.
