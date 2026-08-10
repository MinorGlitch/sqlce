import decimal
import math
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from sqlce import FormatVersion
from sqlce import SqlceDatabase
from tests.infrastructure.sdf_factory import SDF_VERSION_35
from tests.infrastructure.sdf_factory import SDF_VERSION_40
from tests.infrastructure.sdf_factory import list_tables_via_runtime
from tests.infrastructure.sdf_factory import open_connection
from tests.infrastructure.sdf_factory import read_rows_via_runtime
from tests.infrastructure.table_spec import assert_table_matches_runtime

CUSTOM_SDF_DIR_NAME = "custom_sdf"

_RUNTIME_VERSION_BY_FORMAT_VERSION = {
    FormatVersion.SQLCE_35: SDF_VERSION_35,
    FormatVersion.SQLCE_35_SP2: SDF_VERSION_35,
    FormatVersion.SQLCE_40: SDF_VERSION_40,
}


def custom_sdf_dir(base_dir: Path) -> Path:
    return base_dir / CUSTOM_SDF_DIR_NAME


def discover_custom_sdf_files(base_dir: Path) -> List[Path]:
    directory = custom_sdf_dir(base_dir)
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.sdf"))


def runtime_version_for_file(path: Path) -> str:
    format_version = SqlceDatabase.get_format_version_from_file(str(path))
    return _RUNTIME_VERSION_BY_FORMAT_VERSION[format_version]


def _normalize_cell(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return ("decimal", value.normalize())
    if isinstance(value, float):
        if math.isnan(value):
            return ("float", "nan")
        return ("float", value)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (bytes, bytearray)):
        return ("bytes", bytes(value))
    return value


def _normalize_row(row: Dict[str, Any]) -> Tuple[Tuple[str, Any], ...]:
    return tuple(sorted((key, _normalize_cell(value)) for key, value in row.items()))


def _row_multiset(rows: List[Dict[str, Any]]) -> Dict[Tuple[Tuple[str, Any], ...], int]:
    counts: Dict[Tuple[Tuple[str, Any], ...], int] = {}
    for row in rows:
        key = _normalize_row(row)
        counts[key] = counts.get(key, 0) + 1
    return counts


def assert_table_rows_match_runtime(connection, native_db, table_name: str) -> None:
    native_rows = native_db.read_table(table_name)
    runtime_rows = read_rows_via_runtime(connection, table_name)

    native_counts = _row_multiset(native_rows)
    runtime_counts = _row_multiset(runtime_rows)

    if native_counts == runtime_counts:
        return

    missing_in_runtime: List[Tuple[Tuple[str, Any], ...]] = []
    for key, count in native_counts.items():
        deficit = count - runtime_counts.get(key, 0)
        missing_in_runtime.extend([key] * max(deficit, 0))

    extra_in_runtime: List[Tuple[Tuple[str, Any], ...]] = []
    for key, count in runtime_counts.items():
        surplus = count - native_counts.get(key, 0)
        extra_in_runtime.extend([key] * max(surplus, 0))

    raise AssertionError(
        f"row content mismatch for table {table_name!r}\n"
        f"rows only in sqlce lib ({len(missing_in_runtime)}):  {missing_in_runtime}\n"
        f"rows only in dll runtime ({len(extra_in_runtime)}): {extra_in_runtime}"
    )


def assert_runtime_matches_native(path: Path) -> None:
    native_db = SqlceDatabase(str(path))
    native_tables = sorted(native_db.list_tables())

    version = runtime_version_for_file(path)
    connection = open_connection(path, None, version)
    try:
        runtime_tables = sorted(list_tables_via_runtime(connection))
        only_in_native = sorted(set(native_tables) - set(runtime_tables))
        only_in_runtime = sorted(set(runtime_tables) - set(native_tables))
        assert native_tables == runtime_tables, (
            f"table list mismatch for {path}\n"
            f"sqlce lib tables:  {native_tables}\n"
            f"dll runtime tables: {runtime_tables}\n"
            f"only in sqlce lib:  {only_in_native}\n"
            f"only in dll runtime: {only_in_runtime}"
        )

        for table_name in native_tables:
            try:
                assert_table_matches_runtime(connection, native_db, table_name)
            except AssertionError as error:
                raise AssertionError(f"schema mismatch for table {table_name!r} in {path}: {error}") from error

            try:
                assert_table_rows_match_runtime(connection, native_db, table_name)
            except AssertionError as error:
                raise AssertionError(f"row mismatch for table {table_name!r} in {path}: {error}") from error
    finally:
        connection.Close()
