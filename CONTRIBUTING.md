# Contributing

Contributions that improve the scientific checks, data provenance, documentation, or usability are welcome. For a substantial change, open an issue first so the approach can be discussed.

## Set up the project

```bash
git clone https://github.com/ranajahanzaib/plasma-shot-inspector.git
cd plasma-shot-inspector
make setup
```

Create a topic branch for your change:

```bash
git switch -c describe-your-change
```

## Make and verify a change

- Follow the existing Python and TypeScript conventions.
- Add or update deterministic tests for changed scientific rules and edge cases.
- Preserve source values and ordering. Do not silently repair, interpolate, or impute measurements.
- Keep data-source assumptions and provenance visible in findings and documentation.
- Do not commit credentials, local environment files, downloaded datasets, local databases, or generated audit reports.
- Update the README when user-facing behavior, supported data, setup, or limitations change.

Run the relevant checks before opening a pull request:

```bash
make test
make lint
make typecheck
make build
```

## Submit a contribution

Push your branch to your fork and open a pull request against this repository. Describe the user or scientific problem, summarize the change, and include the checks you ran. For scientific changes, explain the assumptions and provide test cases that make the expected behavior reproducible.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Bug reports and feature requests can be filed through the repository's GitHub issue templates.
