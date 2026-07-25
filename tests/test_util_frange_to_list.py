import pytest

from util_frange_to_list import frange_to_list


@pytest.mark.parametrize('frange,expected', [
    ('1', [1]),
    ('1-5', [1, 2, 3, 4, 5]),
    ('1,3,5', [1, 3, 5]),
    ('1-3,5', [1, 2, 3, 5]),
    ('1-3,5-7', [1, 2, 3, 5, 6, 7]),
])
def test_frange_to_list(frange, expected):
    assert frange_to_list(frange) == expected


def test_frange_rejects_invalid_characters():
    with pytest.raises(ValueError):
        frange_to_list('1-3;5')


def test_frange_rejects_reversed_range():
    with pytest.raises(ValueError):
        frange_to_list('5-1')


def test_frange_rejects_incomplete_range():
    with pytest.raises(ValueError):
        frange_to_list('1-')
