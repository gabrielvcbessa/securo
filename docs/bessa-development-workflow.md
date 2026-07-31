# Personal integration and upstream contribution workflow

`bessa/main` is the deployable personal integration branch. It combines
personal features that may never be appropriate upstream with upstream-ready
changes that are still being tested together.

## Branch rules

- Never develop directly on `bessa/main`.
- Personal features branch from the latest `origin/bessa/main`.
- Upstream proposals branch from the latest `upstream/main`, not from
  `bessa/main`, so their diffs stay reviewable and free of personal deployment
  assumptions.
- Keep `upstream` fetch-only. Push personal work only to `origin`.
- Merge a validated personal feature into `bessa/main` with a merge commit or a
  traceable squash commit.
- Tag `bessa/main` before schema migrations or deployment changes.

Examples:

```bash
git fetch origin upstream

# Personal feature
git switch bessa/main
git pull --ff-only origin bessa/main
git switch -c bessa/feature-name

# Upstream proposal
git switch -c codex/upstream-feature upstream/main
```

## Required checks

Pull requests into either `main` or `bessa/main` run:

- backend Ruff and the backend test suite with coverage
- frontend lint, type-check, production build, and tests
- committed OpenAPI freshness and compatibility checks

Do not merge when any required check is missing or red. Protect `bessa/main`
in the personal fork with pull requests, required CI and API Contract checks,
and disallow force pushes.

## Delivery

After merging to `bessa/main`:

1. Build both images for the exact merge commit.
2. Deploy only the immutable `sha-<40-character-commit>` tag.
3. Verify `/api/health`, login, Accounts, Transactions, and Reports.
4. Keep the previous image tag until the new version has been exercised.

Upstream work follows a separate path:

1. Rebase the focused branch on `upstream/main`.
2. Run the full relevant suite.
3. Push the focused branch to `origin`.
4. Open a PR from `gabrielvcbessa:<branch>` to
   `securo-finance/securo:main`.
5. Include motivation, behavior, migration/compatibility impact, and exact
   test evidence in the PR body.
