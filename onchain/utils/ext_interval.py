from opshin.ledger.interval import *


def compare_upper_lower_bound(a: UpperBoundPOSIXTime, b: LowerBoundPOSIXTime) -> int:
    # a < b: 1
    # a == b: 0
    # a > b: -1
    result = compare_extended(a.limit, b.limit)
    if result == 0:
        a_closed = get_bool(a.closed)
        b_closed = get_bool(b.closed)
        if a_closed and b_closed:
            result = 0
        else:
            result = 1
    return result


def compare_lower_upper_bound(a: LowerBoundPOSIXTime, b: UpperBoundPOSIXTime) -> int:
    # a < b: 1
    # a == b: 0
    # a > b: -1
    result = compare_extended(a.limit, b.limit)
    if result == 0:
        a_closed = get_bool(a.closed)
        b_closed = get_bool(b.closed)
        if a_closed and b_closed:
            result = 0
        else:
            result = -1
    return result


def entirely_after(a: POSIXTimeRange, b: POSIXTimeRange) -> bool:
    """Returns whether all of a is after b. |---b---| |---a---|"""
    return compare_lower_upper_bound(a.lower_bound, b.upper_bound) == -1


def entirely_before(a: POSIXTimeRange, b: POSIXTimeRange) -> bool:
    """Returns whether all of a is before b. |---a---| |---b---|"""
    return compare_upper_lower_bound(a.upper_bound, b.lower_bound) == 1


def before_ext(a: POSIXTimeRange, b: ExtendedPOSIXTime) -> bool:
    """Returns whether all of a is before b. |---a---| b"""
    return (
        compare_upper_lower_bound(a.upper_bound, LowerBoundPOSIXTime(b, TrueData()))
        == 1
    )


def after_ext(a: POSIXTimeRange, b: ExtendedPOSIXTime) -> bool:
    """Returns whether all of a is after b. b |---a---|"""
    return (
        compare_upper_lower_bound(UpperBoundPOSIXTime(b, TrueData()), a.lower_bound)
        == 1
    )


def contained_ext(a: POSIXTimeRange, b: ExtendedPOSIXTime) -> bool:
    """Returns whether b is (not necessarily strictly) contained in a. |- b --a---|"""
    return not before_ext(a, b) and not after_ext(a, b)


def ext_after_ext(a: ExtendedPOSIXTime, b: ExtendedPOSIXTime) -> bool:
    """
    Check if a is after b, i.e b a
    """
    return compare_extended(a, b) == -1


def range_is_short(a: POSIXTimeRange, max_length: int) -> bool:
    "Returns whether the range is at most max_length (in milliseconds)."
    if not isinstance(a.upper_bound.limit, FinitePOSIXTime):
        return False
    if not isinstance(a.lower_bound.limit, FinitePOSIXTime):
        return False
    return a.upper_bound.limit - a.lower_bound.limit <= max_length
