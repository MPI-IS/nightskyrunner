from functools import partial

from nightskyrunner import compare


def test_compare():
    def f1(a: str, b: int) -> str:
        return f"{a} {b}"

    p11 = partial(f1, "p11")
    p11_bis = partial(f1, "p11")
    p12 = partial(f1, "p12")

    a11 = {1: 1, 2: {2: 2, "f": p11, 3: [1, 2, p11]}, 3: f1}
    a12 = {1: 1, 2: {2: 2, "f": p11_bis, 3: [1, 2, p11_bis]}, 3: f1}

    assert compare.compare_kwargs(a11, a12)

    a2 = {1: 1, 2: {2: 2, "f": p11, 3: [1, 2, p12]}, 3: f1}

    a3 = {1: 2, 2: {2: 2, "f": p11, 3: [1, 2, p11]}, 3: f1}

    a4 = {1: 1, 2: {2: 2, "f": p11, 3: [1, p11]}, 3: f1}

    a5 = {1: 1, 2: {2: 2, "f": p11, 3: [1, 2, p11]}, 3: f1, 4: 4}

    a6 = {1: 1, 2: {2: 2, "f": p11, 3: [1, 2, p11, 4]}, 3: f1}

    for a in (a2, a3, a4, a5, a6):
        assert not compare.compare_kwargs(a11, a)
