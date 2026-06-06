"""Run official public memory benchmark smoke slices.

This script is a thin CLI wrapper. The reusable orchestration lives in
``memo_stack_server.official_public_benchmark`` so full-provider canaries can
share the same implementation.
"""

from memo_stack_server.official_public_benchmark import main

if __name__ == "__main__":
    raise SystemExit(main())
