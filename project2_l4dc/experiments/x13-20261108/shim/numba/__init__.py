"""Stand-in for numba (PyPI unreachable in this environment): njit returns the Python function unchanged.
The frozen engine source is not modified; only its @njit loops run uncompiled."""
def njit(*args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
    return lambda f: f
