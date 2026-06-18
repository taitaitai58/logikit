# Test package for logikit.
#
# Tests use only the standard-library ``unittest`` framework (the project's core
# is dependency-free, and so is its test suite — CI needs nothing but Python).
# Run from the repo root with:
#
#     python -m unittest discover -s tests -v        (or: make test)
import contextlib
import io
import os
import sys

# Allow `import logikit` / `import examples` straight from a checkout, regardless
# of where the test runner is invoked from.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


@contextlib.contextmanager
def quiet():
    """Swallow stdout (check/sim/truth_table are chatty) and expose the text.

    Usage::

        with quiet() as out:
            check('foo', d)
        self.assertIn('OK', out.getvalue())
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf
