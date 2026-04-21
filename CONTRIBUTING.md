# Contributing to AI Manifest

Thanks for considering contributing. This project is an open protocol for AI agents on the web, and we welcome input from website operators, agent implementers, security researchers, and spec enthusiasts.

## How to Contribute

### 1. Reporting Issues
Use [GitHub Issues](https://github.com/11pyo/AINavManifest/issues) and pick the right template:
- **Bug report** — something broken in the reference implementation
- **Feature request** — new capability you'd like to see
- **Schema proposal** — new field, new action type, or semantic change
- **Question** — open-ended discussion

### 2. Pull Requests
- Fork the repo, create a feature branch (`feat/…`, `fix/…`, `docs/…`)
- Keep changes focused — one concern per PR
- Include reasoning in the PR description (the *why*, not just the *what*)
- Run the benchmark before and after if you're touching the agent or server code

### 3. Schema Changes
Schema changes are the highest-impact contributions. Please:
1. Open a **Schema proposal** issue first to discuss
2. After rough consensus, submit a PR updating `ai-manifest.schema.json` + at least one example in `examples/`
3. Bump the `version` field in the schema if breaking
4. The IETF Internet-Draft may also need updating — note this in the PR

### 4. Benchmark Contributions
Additional scenarios (e.g. SAP transaction codes, ScholarOne submission, government e-services) are very welcome. Drop them in `validation/` with a self-contained runner.

## Patent & Licensing

- **Code and schema**: MIT License (see `LICENSE`)
- **Essential patent claims**: Offered under FRAND terms (see [`docs/FRAND.md`](docs/FRAND.md))
- By submitting a PR, you grant the repository maintainer a license to use your contribution under the same MIT + FRAND umbrella.
- If your contribution implements or relies on a patent you hold, please disclose it in the PR description so we can discuss FRAND reciprocity.

## Code of Conduct

By participating, you agree to uphold the [Code of Conduct](CODE_OF_CONDUCT.md).

## Communication

- **GitHub Issues** — primary discussion channel, public archive
- **Email** — <pk102h@naver.com> for licensing, coordinated disclosure, or private matters

## Looking for a First Contribution?

- Add a new example manifest for a real web app you use
- Translate the README to another language
- Improve the JSON Schema error messages
- File benchmarks on your own hardware and share results
- Review the IETF Internet-Draft and file clarity/consistency issues

Thank you.
