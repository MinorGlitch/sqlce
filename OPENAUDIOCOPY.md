# SQLCE reader used by OpenAudioCopy

This is the `openaudiocopy` branch of https://github.com/MinorGlitch/sqlce,
forked from https://github.com/boykopovar/sqlce at
`78a3888b028952e0157bde1d1fd0a7b30edc4747` (version 0.3.1, MIT).
The upstream copyright and license remain in `LICENSE`.

The `fix/parser-bounds` branch contains the general reader fixes intended for
upstream review: fixed-width buffer checks, page/slot validation, and LOB length
and chunk validation. Its synthetic native tests run without SQL Server CE or
private databases. The normal damaged-row recovery behavior is preserved there.

This branch adds OpenAudioCopy's strict live-row validation and the distribution
name `openaudiocopy-sqlce`, version `0.3.1.post1`. The Python import remains
`sqlce`. Both downstream changes are separate commits and are excluded from the
upstream candidate. They are application policy, not required upstream fixes.

OpenAudioCopy pins this repository as the `vendor/sqlce` Git submodule. The
parent repository's gitlink fixes the source revision. Its uv workspace builds
the application and reader wheels together with `uv build --all-packages`.
Installing the application wheel from an index cannot silently substitute the
unpatched `sqlce` distribution.

OpenAudioCopy currently imports only unencrypted SQLCE 3.5/3.5 SP2 files. The
reader runs in a bounded child process. These fixes and regression tests cover
specific parser failures; they are not a complete parser audit.

To run the portable native regressions:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release --target binary_reader_test page_view_test lob_chain_test
ctest --test-dir build/core -C Release --output-on-failure -R '^(binary_reader|page_view|lob_chain)_test$'
```

The native bounds workflow also runs ASan and UBSan. The separate upstream
Python integration suite requires the original SQLCE runtimes on Windows.
