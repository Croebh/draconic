import pytest

from draconic import DraconicInterpreter
from draconic.exceptions import *
from draconic.helpers import DraconicConfig


@pytest.fixture()
def i():
    # 1000-size iterables, don't limit us by loops, signed 32b int limit
    config = DraconicConfig(max_loops=99999999, max_const_len=1000, max_int_size=32)
    return DraconicInterpreter(config=config)


def test_creating(i, e):
    really_long_str = 'foo' * 1000
    not_quite_as_long = 'f' * 999

    i._names['long'] = really_long_str
    i._names['lesslong'] = not_quite_as_long

    # strings
    with pytest.raises(IterableTooLong):
        e(f"'{really_long_str}'")

    # lists
    with pytest.raises(FeatureNotAvailable):  # we don't allow this
        e(f"[*long, *long]")


def test_list(i, e):
    e("long = [1] * 1000")

    with pytest.raises(IterableTooLong):
        e("long.append(1)")

    with pytest.raises(IterableTooLong):
        e("long.extend([1])")

    with pytest.raises(IterableTooLong):
        e("long.extend(long)")

    # we should always be operating using safe lists
    i.builtins['reallist'] = [1, 2, 3]
    e("my_list = [1, 2, 3]")
    assert isinstance(e("my_list + reallist"), i._list)
    assert isinstance(e("reallist + my_list"), i._list)
    e("my_list.extend(reallist)")
    assert isinstance(e("my_list"), i._list)


def test_set(i, e):
    i.builtins['range'] = range
    e("long = set(range(1000))")
    e("long2 = set(range(1000, 2000))")

    with pytest.raises(IterableTooLong):
        e("long.add(1000)")

    with pytest.raises(IterableTooLong):
        e("long.update(long2)")

    with pytest.raises(IterableTooLong):
        e("long.union(long2)")

    with pytest.raises(IterableTooLong):
        e("long.update({1000})")

    # we should always be operating using safe sets
    i.builtins['realset'] = {1, 2, 3}
    e("my_set = {3, 4, 5}")
    # these operations don't work because sets use bitwise ops and we don't allow those
    # assert isinstance(e("my_set | realset"), i._set)
    # assert isinstance(e("realset | my_set"), i._set)
    e("my_set.update(realset)")
    assert isinstance(e("my_set"), i._set)
    assert isinstance(e("my_set.union(realset)"), i._set)


def test_dict(i, e):
    i.builtins['range'] = range
    e("long = dict((i, i) for i in range(1000))")
    e("long2 = {i: i for i in range(1000, 2000)}")

    with pytest.raises(IterableTooLong):
        e("long.update(long2)")

    with pytest.raises(IterableTooLong):
        e("long.update({'foo': 'bar'})")


def test_that_it_still_works_right(i, e):
    e("l = [1, 2]")
    e("d = {1: 1}")
    e("s = {1, 2}")

    e("l.append(3)")
    assert e("l") == [1, 2, 3]
    assert isinstance(i.names['l'], i._list)

    e("s.add(3)")
    assert e("s") == {1, 2, 3}
    assert isinstance(i.names['s'], i._set)

    e("d.update({2: 2})")
    assert e("d") == {1: 1, 2: 2}
    assert isinstance(i.names['d'], i._dict)


def test_types(i, e):
    # when we have a compound type as a builtin, users shouldn't be able to modify it directly...
    i.builtins.update({'rl': [1, 2], 'rd': {1: 1, 2: 2}})

    e("rl[1] = 3")
    e("rd[2] = 3")

    assert i.names['rl'] == [1, 2]
    assert i.names['rd'] == {1: 1, 2: 2}

    # but setting it to a name is fine
    e("l = rl")
    e("d = rd")

    e("l[1] = 3")
    e("d[2] = 3")

    assert i.names['l'] == [1, 3]
    assert i.names['d'] == {1: 1, 2: 3}


def test_types_again(i, e):
    e("a = [1, 2, 3]")
    e("b = list('123')")
    assert type(i.names['a']) is type(i.names['b']) is i._list

    e("a = {1, 2, 3}")
    e("b = set('123')")
    assert type(i.names['a']) is type(i.names['b']) is i._set

    e("a = {1: 1, 2: 2}")
    e("b = dict(((1, 1), (2, 2)))")
    assert type(i.names['a']) is type(i.names['b']) is i._dict

    e("a = 'foobar'")
    e("b = str(123)")
    assert type(i.names['a']) is type(i.names['b']) is i._str

    i.builtins['typeof'] = lambda o: type(o).__name__
    assert e('typeof(a)') == 'str'


def test_int_limits(e):
    max_int = (2 ** 31) - 1
    min_int = -(2 ** 31)
    e(f"max_int = {max_int}")
    e(f"min_int = {min_int}")

    # result is too large
    with pytest.raises(NumberTooHigh):
        e("max_int + 1")

    with pytest.raises(NumberTooHigh):
        e("max_int - -1")

    with pytest.raises(NumberTooHigh):
        e("max_int * 2")

    with pytest.raises(NumberTooHigh):
        e("max_int << 1")

    with pytest.raises(NumberTooHigh):
        e("max_int * max_int")

    with pytest.raises(NumberTooHigh):
        e("2 ** 31")

    with pytest.raises(NumberTooHigh):
        e("2 << 31")

    with pytest.raises(NumberTooHigh):
        e("min_int - 1")

    with pytest.raises(NumberTooHigh):
        e("min_int + -1")

    with pytest.raises(NumberTooHigh):
        e("min_int * 2")

    with pytest.raises(NumberTooHigh):
        e("min_int << 1")

    with pytest.raises(NumberTooHigh):
        e("min_int * -min_int")


def test_int_limits_one_op(e):
    max_int = (2 ** 31) - 1
    min_int = -(2 ** 31)
    e(f"max_int = {max_int}")
    e(f"min_int = {min_int}")

    # one operand is too large
    e(f"over_max_int = {max_int + 1}")
    e(f"under_min_int = {min_int - 1}")

    with pytest.raises(NumberTooHigh):
        e("over_max_int - 1")

    with pytest.raises(NumberTooHigh):
        e("1 - over_max_int")

    with pytest.raises(NumberTooHigh):
        e("over_max_int + -1")

    with pytest.raises(NumberTooHigh):
        e("-1 + over_max_int")

    with pytest.raises(NumberTooHigh):
        e("over_max_int * 1")

    with pytest.raises(NumberTooHigh):
        e("1 * over_max_int")

    with pytest.raises(NumberTooHigh):
        e("under_min_int - 1")

    with pytest.raises(NumberTooHigh):
        e("1 - under_min_int")

    with pytest.raises(NumberTooHigh):
        e("under_min_int + -1")

    with pytest.raises(NumberTooHigh):
        e("-1 + under_min_int")

    with pytest.raises(NumberTooHigh):
        e("under_min_int * 1")

    with pytest.raises(NumberTooHigh):
        e("1 * under_min_int")


def test_int_limits_not_floats(e):
    max_int = (2 ** 31) - 1
    min_int = -(2 ** 31)
    e(f"max_int = {max_int}")
    e(f"min_int = {min_int}")

    # floats are fine
    assert e("max_int * 1.5") == max_int * 1.5
    assert e("max_int / 0.5") == max_int / 0.5
    assert e("max_int // 0.5") == max_int // 0.5
    assert type(e("max_int // 0.5")) is float

    assert e("min_int * 1.5") == min_int * 1.5
    assert e("min_int / 0.5") == min_int / 0.5
    assert e("min_int // 0.5") == min_int // 0.5
    assert type(e("min_int // 0.5")) is float


@pytest.mark.timeout(3)  # list mult should be fast, even if we do it a lot
def test_list_mult_speed():
    config = DraconicConfig(max_loops=10000, max_const_len=10000)
    i = DraconicInterpreter(config=config)
    expr = """
    while True:
        a = [0] * 10000
    """.strip()
    with pytest.raises(TooManyStatements):
        i.execute(expr)
