"""Định dạng số theo cách trình bày bài giải hóa học."""

from decimal import Decimal
from fractions import Fraction


def to_fraction(value) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    text = str(value).strip().replace(",", ".")
    return Fraction(text)


def format_number(value) -> str:
    """In số với dấu phẩy thập phân, bỏ phần thập phân thừa."""
    fraction = to_fraction(value)
    if fraction.denominator == 1:
        return str(fraction.numerator)

    denominator = fraction.denominator
    while denominator % 2 == 0:
        denominator //= 2
    while denominator % 5 == 0:
        denominator //= 5
    if denominator == 1:
        decimal = Decimal(fraction.numerator) / Decimal(fraction.denominator)
        text = format(decimal, "f")
    else:
        decimal = (Decimal(fraction.numerator) / Decimal(fraction.denominator)).quantize(Decimal("0.0001"))
        text = format(decimal, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def format_fraction_value(value) -> str:
    fraction = to_fraction(value)
    if fraction.denominator == 1:
        return str(fraction.numerator)
    return f"{fraction.numerator}/{fraction.denominator}"
