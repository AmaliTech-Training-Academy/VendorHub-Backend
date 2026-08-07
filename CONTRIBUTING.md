# Contributing

## Branch Naming
Branches must follow the pattern `<type>/<short-description>`.

### Branch Types

| Type | Use |
|---|---|
| **`feat/`** | New feature |
| **`fix/`** | Bug fix |
| **`chore/`** | Maintenance or dependency updates |
| **`docs/`** | Documentation-only changes |
| **`refactor/`** | Code restructuring without behavior changes |
| **`test/`** | Adding or fixing tests |
| **`hotfix/`** | Urgent production fix |

### Examples

```text
feat/user-authentication
fix/null-pointer-on-login
docs/update-api-reference
refactor/payment-service
test/user-registration
hotfix/payment-processing
```

### Branch Naming Rules

- Use **lowercase** characters only.
- Use **hyphens (`-`)** as word separators.
- Do not use underscores (`_`) or spaces.
- Keep branch names short but descriptive, ideally **3–6 words**.
- Include a ticket or issue number when applicable.

For example:

```text
feat/AUTH-42-user-authentication
fix/API-17-invalid-token
```

- Branch from **`main`** by default.
- If the project uses **Gitflow**, branch from **`develop`** instead.

## Commit Messages

This project follows the widely adopted **[Conventional Commits](https://www.conventionalcommits.org/)** specification.

Use the following format:

```text
<type>(<optional scope>): <short summary>

<optional body>

<optional footer>
```

### Commit Types

| Type | Use |
|---|---|
| **`feat`** | Introduces a new feature |
| **`fix`** | Fixes a bug |
| **`docs`** | Documentation changes |
| **`refactor`** | Code restructuring without behavior changes |
| **`test`** | Adds or modifies tests |
| **`chore`** | Maintenance tasks or dependency updates |
| **`perf`** | Performance improvements |
| **`build`** | Build system or dependency changes |
| **`ci`** | CI/CD configuration changes |

### Examples

```text
feat(auth): add JWT token refresh logic

fix(api): handle 404 when user not found

docs: add branch naming section to CONTRIBUTING.md

chore(deps): upgrade axios to 1.7.2

refactor(users): simplify user lookup service

test(auth): add refresh token tests
```

### Commit Message Rules

- Write the subject in **imperative mood**.
- Do not end the subject with a full stop.
- Keep the subject line to a maximum of **72 characters**.
- Use the body when additional context is necessary.
- The body should explain **why** the change was made rather than simply describing **what** changed. The diff already shows what changed.
- Use the footer to reference related issues or tickets.

For example:

```text
feat(auth): add refresh token rotation

Improve token security by rotating refresh tokens after
each successful refresh operation.

Closes #42
Refs #17
```

### Merge Commits

Avoid unnecessary merge commit messages such as:

```text
Merged branch X into Y
```

Prefer **squash merging** or **rebase merging** according to the project's repository settings and team workflow.

## Pull Requests
- All changes to `main` require at least one approving review.
- Resolve all review comments before merging.
- Keep PRs focused; one concern per PR.
