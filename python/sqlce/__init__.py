import datetime
import decimal
import uuid
from typing import Dict, Union

from sqlce._sqlce_native import ColumnSchema
from sqlce._sqlce_native import EncryptionMode
from sqlce._sqlce_native import FormatVersion
from sqlce._sqlce_native import InvalidPasswordError
from sqlce._sqlce_native import LazyLob
from sqlce._sqlce_native import SqlceDatabase
from sqlce._sqlce_native import TableRowIterator
from sqlce._sqlce_native import UnsupportedEncryptionModeError

ColumnValue = Union[
    None,
    int,
    float,
    bool,
    str,
    bytes,
    datetime.datetime,
    decimal.Decimal,
    uuid.UUID,
    LazyLob,
]
Row = Dict[str, ColumnValue]

__all__ = [
    "ColumnSchema",
    "ColumnValue",
    "EncryptionMode",
    "FormatVersion",
    "InvalidPasswordError",
    "LazyLob",
    "Row",
    "SqlceDatabase",
    "TableRowIterator",
    "UnsupportedEncryptionModeError",
]
