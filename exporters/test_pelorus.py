import pytest
import pelorus


@pytest.mark.parametrize("start_time,end_time",
                         [
                            ('2020-06-27T03:17:8Z', '2020-06-27T06:17:8Z')
                         ]
                         )
def test_convert_date_time_to_timestamp(start_time, end_time):
    start_timestamp = 1593227828
    end_timestamp = 1593238628
    three_hours = 10800

    calc_start = pelorus.convert_date_time_to_timestamp(start_time)
    assert calc_start == start_timestamp
    calc_end = pelorus.convert_date_time_to_timestamp(end_time)
    assert calc_end == end_timestamp
    assert calc_end - calc_start == three_hours
