# Development Guidelines & Conventions

This document defines the development workflows, architectural rules, and engineering standards for the **SIH26100** monorepo.

---

## 1. Git Workflow & Branching Strategy

We follow a structured Git branching model to ensure stability and clean release cycles:

- `main`: Production-ready branch. Only merges from `develop` via pull requests.
- `develop`: Primary integration branch for active development.
- `feature/<feature-name>`: Dedicated branch for new features (e.g., `feature/document-parser`). Branched from `develop` and merged back into `develop`.
- `fix/<bug-name>`: Bugfix branches for resolving defects (e.g., `fix/health-endpoint-status`).
- `hotfix/<issue-name>`: Critical fixes applied directly to `main` and back-ported to `develop`.

---

## 2. Commit Message Conventions

We strictly follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<optional scope>): <description>
```

### Allowed Types
- `feat`: A new feature or capability
- `fix`: A bug fix
- `docs`: Documentation changes only
- `test`: Adding or refactoring tests
- `refactor`: Code changes that neither fix a bug nor add a feature
- `chore`: Build process, tooling, or dependency updates

### Examples
- `feat: add document upload API endpoint`
- `fix: correct health endpoint status code`
- `docs: update README with local setup instructions`
- `test: add health endpoint unit tests`
- `refactor: modularize settings and configuration`
- `chore: update Docker configuration`

---

## 3. Python Coding Standards

- **Style Guide**: Follow [PEP 8](https://peps.python.org/pep-0008/) style standards.
- **Type Annotations**: Provide explicit type hints for function arguments and return types.
- **Modularity**: Keep functions and modules focused on a single responsibility. Avoid monolithic files.
- **State Management**: Do not introduce unnecessary global mutable state.
- **Environment & Config**: Access settings strictly through `app.config.settings` rather than direct `os.getenv` calls across arbitrary files.

---

## 4. TypeScript & React Standards

- **TypeScript Strictness**: Keep `strict: true` enabled in compiler configuration. Avoid `any`; use precise types, interfaces, or generic parameters.
- **Functional Components**: Write React components using functional syntax and hooks.
- **Component Naming**: Use PascalCase for component files and symbols (e.g., `App.tsx`, `Header.tsx`).
- **CSS & Styling**: Keep styles scoped, responsive, and accessible with semantic HTML elements.

---

## 5. API Design Conventions

- **RESTful Principles**: Resource-oriented URLs using standard HTTP methods (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`).
- **HTTP Status Codes**: Use appropriate status codes (e.g., `200 OK`, `201 Created`, `400 Bad Request`, `404 Not Found`, `422 Unprocessable Entity`, `500 Internal Server Error`).
- **JSON Payloads**: Standardize response formats and error schemas across all endpoints.
- **OpenAPI / Swagger**: Ensure every route has clear docstrings and descriptions to auto-generate comprehensive OpenAPI docs via FastAPI.

---

## 6. Security Rules

- **Zero Secrets in Version Control**: Never commit credentials, passwords, private keys, API tokens, database credentials, or JWT signing secrets.
- **Environment Management**: Keep configuration in `.env` (which is git-ignored) and document keys in `.env.example`.
- **Validation**: Validate all incoming requests and payloads using Pydantic models.

---

## 7. Testing Strategy

- **Backend**: Every endpoint and core utility must have corresponding automated tests in `backend/tests/` executed via `pytest`.
- **Reproducibility**: Tests must pass locally and in CI environments without external third-party dependencies during base testing.

---

## 8. Docker & Containerization

- Keep builds lightweight, multi-stage where appropriate, and reproducible.
- Ensure the application runs seamlessly from root using:
  ```bash
  docker compose build
  docker compose up
  ```
