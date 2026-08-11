import datetime
import decimal
import enum
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import Union
from typing import overload
import uuid

class LazyLob:
    """
    Lazy reference to a LOB value (NText or Image) of a table row.
    Holds the read source (LOB chain pages), not the data itself.
    """

    def read(self) -> Union[str, bytes]:
        """
        Reads the entire value at once.

        Returns:
            str if the column is NText (after UTF-16LE or Latin1
            decoding, depending on the value's compression flag).
            bytes if the column is Image.

        Complexity:
            O(L), L - value length in bytes. For a non-inline value,
            the number of PageBytes accesses equals the number of pages
            in the LOB chain (chunk = payload of one page minus the
            LOB page header). Each access is served from the storage
            cache or from disk.
        """
        ...

    def read_chunks(self) -> List[bytes]:
        """
        Reads the value in parts, without decoding and without
        assembling it into a single string.

        Returns:
            A list of bytes. For a non-inline value - one element per
            page of the LOB chain. For an inline value - a list with
            one element (or an empty list if the value is empty).

        Complexity:
            O(L) total, O(1) per chunk.
        """
        ...


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
"""
Value of a single row column after decoding.

None: NULL (the row's presence-mask bit is set).
int: TinyInt, SmallInt, Int, BigInt.
float: Real, Float, Money (money = raw_int64 / 10000).
bool: Bit.
str: NVarChar (variable length; may be Latin1-compressed per the
    var-directory flag) and NChar (fixed length; always UTF-16LE,
    the compression flag does not apply to it).
bytes: Binary, VarBinary, RowVersion, and any column type outside the
    known code range (unrecognized type).
datetime.datetime: DateTime, assembled from a day count since
    1900-01-01 and ticks (1/300 second) since midnight.
decimal.Decimal: Numeric, reconstructed from the catalog's precision,
    scale, sign, and little-endian unscaled digits.
uuid.UUID: UniqueIdentifier, 16 bytes interpreted as bytes_le.
LazyLob: NText and Image - not read while decoding the row.
"""

Row = Dict[str, ColumnValue]
"""Table row: column name -> value, in order of increasing dense ordinal."""


class TableRowIterator:
    """
    Lazy row-by-row iterator returned by SqlceDatabase.iterate_table().
    Holds a reference to the SqlceDatabase object: the database object
    is not destroyed while the iterator is alive.
    """

    def __iter__(self) -> "TableRowIterator":
        """Returns: self. Complexity: O(1)."""
        ...

    def __next__(self) -> Row:
        """
        Finds and decodes the next table row, starting the search at
        the slot index right after the current position.

        Scans the slots of the current data page; if exhausted, moves
        to the table's next data page. If the found row is fragmented
        across multiple data pages, reassembles it by following the
        chain of continuation slots.

        Returns:
            The decoded row.

        Complexity:
            O(P) worst case (P - number of unscanned data pages before
            the next row), O(1) amortized with densely packed rows.
            O(C) to decode a row's C columns.

        Raises:
            StopIteration: no more rows.
            InvalidSdfError: a row's continuation-slot chain does not
                resolve to the end, or the number of hops along the
                chain exceeds the internal limit.
        """
        ...


class EncryptionMode(enum.Enum):
    """Encryption algorithm for .sdf pages, read from the mode field of page 0."""

    NONE = ...
    """File is not encrypted."""

    TRIPLE_DES_SHA1 = ...
    """Triple DES (24-byte key), key = SHA-1(UTF-16LE(password) || key_param)."""

    AES128_SHA1 = ...
    """AES-128, key = SHA-1(UTF-16LE(password) || key_param)."""

    AES128_SHA256 = ...
    """AES-128, key = SHA-256(UTF-16LE(password) || key_param)."""

    AES256_SHA512 = ...
    """AES-256, key = SHA-512(UTF-16LE(password) || key_param)."""


class FormatVersion(enum.Enum):
    """.sdf format version, read at a fixed offset of page 0."""

    UNKNOWN = ...
    """The version value in the file does not match any known format constant."""

    SQLCE_30 = ...
    """SQL Server Compact 3.0."""

    SQLCE_35 = ...
    """SQL Server Compact 3.5."""

    SQLCE_35_SP2 = ...
    """SQL Server Compact 3.5 Service Pack 2."""

    SQLCE_40 = ...
    """SQL Server Compact 4.0."""


class UnsupportedEncryptionModeError(ValueError):
    """
    Key derivation was requested for EncryptionMode.NONE, which is not
    a key-derivation algorithm. The only public path to reach this:
    verify_password_with_mode(..., mode=EncryptionMode.NONE).
    """
    ...


class InvalidPasswordError(ValueError):
    """
    The password did not match any of the four supported algorithms
    (TRIPLE_DES_SHA1, AES128_SHA1, AES128_SHA256, AES256_SHA512) while
    opening the file, or the file is encrypted and no password was
    given.

    After a SqlceDatabase object has been successfully created, this
    exception cannot occur again from any other method on that object:
    algorithm resolution and verification happen once, in the
    constructor, and the result is cached for the object's lifetime.

    Not raised when the password exceeds the maximum length (40 bytes
    of UTF-16LE-encoded string) - in that case a plain ValueError is
    raised instead.
    """
    ...


class InvalidSdfError(ValueError):
    """
    The .sdf file is structurally invalid: shorter than one page; the
    logical page map (Map A / Map B) is missing or corrupted; a chain
    of row, catalog-row, or LOB-value fragments does not resolve to
    the end, or exceeds the internal hop limit across continuation
    pages. str(error) contains a text description of the specific
    cause.
    """
    ...


class ColumnSchema:
    """
    Description of a single table column from the file's system
    catalog. An immutable snapshot taken at the time table_schema()
    was called.
    """

    @property
    def ordinal(self) -> int:
        """Dense ordinal position of the column in the table, starting at 1, by increasing catalog ordinal."""
        ...

    @property
    def name(self) -> str:
        """Column name, as stored in the system catalog."""
        ...

    @property
    def type_name(self) -> str:
        """SQL Server Compact type name: "int", "nvarchar", "ntext", "image", "uniqueidentifier", etc."""
        ...

    @property
    def declared_size(self) -> Optional[int]:
        """
        Returns:
            NVarChar/NChar: character count (catalog byte size / 2).
            Binary/VarBinary: byte count.
            Image: constant 0x3FFFFFFF.
            NText: constant 0x1FFFFFFF.
            Other types: None.
        """
        ...

    @property
    def precision(self) -> Optional[int]:
        """
        Returns:
            Fixed values: Bit=1, TinyInt=3, SmallInt=5, Int=10,
            BigInt=19, Real=24, Float=53, Money=19, DateTime=23.
            Numeric: value from the catalog.
            Other types: None.
        """
        ...

    @property
    def scale(self) -> Optional[int]:
        """
        Returns:
            Fixed values: Bit=0, Money=4, DateTime=3.
            Numeric: value from the catalog.
            Other types: None.
        """
        ...


class SqlceDatabase:
    """
    Read-only access to a .sdf file. No write methods. Opening
    immediately parses the system catalog and resolves each table's
    data pages; rows are decoded lazily on access.
    """

    @overload
    def __init__(self, path: str) -> None:
        """
        Opens an unencrypted .sdf file.

        On open: page 0 is read, format and encryption mode are
        determined, the logical page map (Map A / Map B) is built, the
        system catalog is parsed, and each table's data pages are
        resolved. The logical page map and the catalog are read once
        and cached for the object's lifetime.

        Args:
            path: path to the .sdf file.

        Complexity:
            O(P/1527 + K + T), where P is the number of pages in the
            file (the Map B page count grows with P, since Map B
            indexes ranges of 1527 logical IDs per page, and every
            page of the file has a logical ID, including table data
            pages), K is the number of heap pages of the system
            catalog, and T is the number of tables (one root page
            each).

            Row bodies (table data pages) are not read at this point -
            only the map of their location is read. So the I/O volume
            on open is 2-3 orders of magnitude smaller than the full
            file size, but is not constant with respect to it: it
            grows linearly with P, with a small coefficient.

        Raises:
            RuntimeError: the file cannot be opened, or its size is
                not a multiple of the page size.
            InvalidPasswordError: the file is password-protected (this
                overload does not accept a password).
            InvalidSdfError: the logical page map or the catalog is
                corrupted.
        """
        ...

    @overload
    def __init__(self, path: str, password: str) -> None:
        """
        Opens an encrypted .sdf file with a known password.

        The file stores a declared encryption algorithm (available via
        get_encryption_mode), but the constructor does not rely on it:
        the password is checked in turn against the page-0 verifier
        for each of the 4 supported algorithms (TRIPLE_DES_SHA1,
        AES128_SHA1, AES128_SHA256, AES256_SHA512), until a match is
        found. The matched algorithm becomes resolved_encryption_mode
        and can, in theory, differ from the one declared in the file.

        Args:
            path: path to the .sdf file.
            password: password, at most 40 bytes after UTF-16LE
                encoding.

        Complexity:
            Algorithm resolution: up to 4 attempts, each - key
            derivation by hashing the password, plus decryption of one
            block of the page-0 verifier. Catalog parsing after that -
            same as the no-password constructor: O(P/1527 + K + T)
            (see that overload for details).

        Raises:
            ValueError: the password exceeds 40 bytes after UTF-16LE
                encoding.
            InvalidPasswordError: the password did not match any of
                the four algorithms (in practice, this means the
                password is wrong).
            InvalidSdfError: the logical page map or the catalog is
                corrupted.
            RuntimeError: the file cannot be opened.
        """
        ...

    def list_tables(self) -> List[str]:
        """
        Returns:
            Names of all user tables from the system catalog, in
            lexicographic order (the traversal order of std::map by
            name).

        Complexity:
            O(T), T - number of tables. No file access: the list was
            assembled by the constructor and is held in the object's
            memory.
        """
        ...

    def table_schema(self, table_name: str) -> List[ColumnSchema]:
        """
        Args:
            table_name: table name.

        Returns:
            Column descriptions in order of increasing ordinal.

        Complexity:
            O(C), C - number of columns in the table. No file pages
            are read.

        Raises:
            IndexError: no table with that name (std::out_of_range at
                the C++ level).
        """
        ...

    def read_table(self, table_name: str) -> List[Row]:
        """
        Reads and decodes all rows of the table at once into a list.
        Equivalent to list(self.iterate_table(table_name)).

        Args:
            table_name: table name.

        Returns:
            A list of rows. LOB columns (NText, Image) are not read
            into memory: the cell holds a LazyLob object instead.

        Complexity:
            O(R*C) in time and memory, R - number of rows, C - number
            of columns; the entire result is held in memory at once.

        Raises:
            IndexError: no table with that name.
            InvalidSdfError: a row's fragment chain is corrupted.
        """
        ...

    def iterate_table(self, table_name: str) -> Iterator[Row]:
        """
        Returns a lazy row-by-row iterator: rows are read and decoded
        one at a time as the iterator is consumed, without
        materializing the whole table in memory.

        Args:
            table_name: table name.

        Returns:
            An iterator holding a reference to self.

        Complexity:
            Creating the iterator: O(1). One step: see
            TableRowIterator.__next__.

        Raises:
            IndexError: no table with that name - raised immediately,
                when this method is called.
            InvalidSdfError: raised lazily, during iteration.
        """
        ...

    def row_count(self, table_name: str) -> int:
        """
        Args:
            table_name: table name.

        Returns:
            Number of rows in the table. If the table's root page
            contains a recognizable cardinality field, the value is
            read directly from that field, without scanning rows. If
            the field is unavailable (the root page is not recognized
            as TableRootPageType, the logical page does not resolve,
            or the page is shorter than the expected field offset), a
            full pass over iterate_table is performed, counting rows
            without decoding column values.

        Complexity:
            O(1) (one root-page read) in the first case - the
            cardinality field is read from the file itself, not from a
            previously stored call result, so the first and subsequent
            calls cost the same. O(R) in the second case, R - number
            of rows, including reassembly of fragmented rows, if any.

        Raises:
            IndexError: no table with that name.
            InvalidSdfError: during a full pass - a row's fragment
                chain is corrupted.
        """
        ...

    def get_encryption_mode(self) -> EncryptionMode:
        """
        Returns:
            The encryption mode declared on the file's page 0,
            regardless of whether a password was given or verified.

        Complexity:
            O(1). The value was computed on open.
        """
        ...

    @staticmethod
    def get_encryption_mode_from_file(path: str) -> EncryptionMode:
        """
        Args:
            path: path to the .sdf file.

        Returns:
            The declared encryption mode. The file is not opened as a
            database: no SqlceDatabase object is created, the catalog
            and the logical page map are not parsed. The file is
            opened with a separate, independent file handle and closed
            right after reading - prior or later calls (including an
            already-open SqlceDatabase for the same file) are not
            affected by this and this handle is not reused by them.

        Complexity:
            O(1) relative to file size - only page 0 is read from
            disk.

        Raises:
            RuntimeError: the file cannot be opened.
            InvalidSdfError: the file is shorter than one page.
        """
        ...

    def resolved_encryption_mode(self) -> EncryptionMode:
        """
        Returns:
            The encryption algorithm actually confirmed by the
            password on open (can, in theory, differ from
            get_encryption_mode if the declared and resolved modes
            diverge). NONE for an unencrypted file.

        Complexity:
            O(1). The value was computed (and, if needed, resolved by
            checking 4 algorithms) in the constructor.
        """
        ...

    def get_format_version(self) -> FormatVersion:
        """
        Returns:
            The format version of the open file, as the value at a
            fixed offset of page 0 (SQLCE_30 / SQLCE_35 / SQLCE_35_SP2
            / SQLCE_40, or UNKNOWN if the value doesn't match any of
            the known constants).

        Complexity:
            O(1). No file access: the value was computed by the
            constructor and is stored in the object.
        """
        ...

    @staticmethod
    def get_format_version_from_file(path: str) -> FormatVersion:
        """
        The same field as get_format_version, but without creating a
        SqlceDatabase object.

        Args:
            path: path to the .sdf file.

        Returns:
            The file's format version (SQLCE_30 / SQLCE_35 /
            SQLCE_35_SP2 / SQLCE_40, or UNKNOWN). The file is not
            opened as a database: no SqlceDatabase object is created,
            the catalog and the logical page map are not parsed.

        Complexity:
            O(1) relative to file size. The file is opened with a
            separate file handle, only page 0 is read from disk, and
            the handle is closed right after reading.

        Raises:
            RuntimeError: the file cannot be opened.
            InvalidSdfError: the file is shorter than one page.
        """
        ...

    def export_decrypted(self) -> bytes:
        """
        Returns:
            The full contents of the file with encryption removed.
            Each page is decrypted (if the file was encrypted); on
            page 0 of the result, the encryption-mode, verifier,
            key-param, provider-info, and "was encrypted" flag fields
            are zeroed out, and page 0's checksum is recomputed. If
            resolved_encryption_mode == NONE, pages are returned as-is
            and page-0 fields are not modified. The file must have
            already been opened by the constructor with the correct
            password.

        Complexity:
            O(P), P - number of pages; each page is decrypted once or
            served from the storage cache. The entire result is held
            in memory at once (P * page_size bytes).
        """
        ...

    @staticmethod
    def verify_password(path: str, password: str) -> bool:
        """
        Checks the password against one of the four supported
        encryption algorithms, without opening the file as a database.
        The check stops at the first algorithm the password matches;
        if it matches none, all four are checked.

        Args:
            path: path to the .sdf file.
            password: password, at most 40 bytes after UTF-16LE
                encoding.

        Returns:
            True if the password matched at least one algorithm
            (correct password). False if it matched none (in
            practice, this means the password is wrong).
            InvalidPasswordError is not raised in that case.

        Complexity:
            1 to 4 verification attempts (see above). Each attempt -
            key derivation by hashing the password, plus decryption of
            one block of the page-0 verifier. Only page 0 is read from
            disk, once, regardless of the number of attempts. O(1).

        Raises:
            ValueError: the password exceeds 40 bytes after UTF-16LE
                encoding.
            RuntimeError: the file cannot be opened.
            InvalidSdfError: the file is shorter than one page.
        """
        ...

    @staticmethod
    def verify_password_with_mode(path: str, password: str, mode: EncryptionMode) -> bool:
        """
        Checks the password against one specific encryption algorithm,
        without opening the file as a database.

        Args:
            path: path to the .sdf file.
            password: password, at most 40 bytes after UTF-16LE
                encoding.
            mode: the algorithm to check against. EncryptionMode.NONE
                is not allowed.

        Returns:
            True if the password matches the specified algorithm.
            False if it does not.

        Complexity:
            O(1), exactly one algorithm is checked.

        Raises:
            UnsupportedEncryptionModeError: mode is EncryptionMode.NONE.
            ValueError: the password exceeds 40 bytes after UTF-16LE
                encoding.
            RuntimeError: the file cannot be opened.
            InvalidSdfError: the file is shorter than one page.
        """
        ...
