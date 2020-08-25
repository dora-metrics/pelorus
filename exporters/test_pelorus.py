import pytest
import pelorus


@pytest.mark.parametrize("start_time,end_time,format",
                         [
                            ('2020-06-27T03:17:8Z', '2020-06-27T06:17:8Z', '%Y-%m-%dT%H:%M:%SZ'),
                            ('2020-06-27T03:17:08.00000-0500', '2020-06-27T06:17:08.000000-0500',
                                                               '%Y-%m-%dT%H:%M:%S.%f%z')
                         ]
                         )
def test_convert_date_time_to_timestamp(start_time, end_time, format):
    start_timestamp = 1593227828
    end_timestamp = 1593238628
    three_hours = 10800

    calc_start = pelorus.convert_date_time_to_timestamp(start_time, format)
    assert calc_start == start_timestamp
    calc_end = pelorus.convert_date_time_to_timestamp(end_time, format)
    assert calc_end == end_timestamp
    assert calc_end - calc_start == three_hours
