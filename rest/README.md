# REST contract tests

Uses Schemathesis to generate and validate requests against the OpenAPI spec.

## Run via CLI (quickest)

```bash
# basic run - checks schemas + no 5xx
schemathesis run openapi.yaml --base-url http://localhost:8080

# all built-in checks (not-a-server-error, status-code-conformance, response-schema-conformance, etc.)
schemathesis run openapi.yaml --base-url http://localhost:8080 --checks all

# against a different env
schemathesis run openapi.yaml --base-url http://staging:8080 --checks all --workers 4
```

## Run via pytest

```bash
# from this directory
pytest test_openapi_contract.py -v

# against a different base url
BASE_URL=http://staging:8080 pytest test_openapi_contract.py -v
```

The pytest tests include some custom assertions on top of schemathesis's built-in schema validation - mostly checking specific fields that other services depend on.

## Notes

- The OpenAPI spec (`openapi.yaml`) is the source of truth. If the service deviates from it, tests should fail.
- Schemathesis uses Hypothesis under the hood to generate edge-case inputs. Run with `--hypothesis-seed=0` for reproducible results.
- If the service isn't running locally, tests will fail with connection errors - that's expected. Point `BASE_URL` at wherever the service is.
