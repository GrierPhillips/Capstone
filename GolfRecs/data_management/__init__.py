"""Initialize data management modules."""

from .utils import (check_pages, get_course_info, get_extras, get_key_info,  # noqa
                    get_layout, get_tee_info, parse_address, parse_review,
                    parse_user_info, renew_connection)
from .data_handler import DataHandler  # noqa
from .data_collector import DataCollector  # noqa
