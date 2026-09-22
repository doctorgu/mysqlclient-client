# Changelog

## [1.2.8]

- Rename *.yml to *.yaml

## [1.2.7]

- Remove use_conditional and make it always to use

## [1.2.6]

- Add list[dict] type to params in updates for executemany support

## [1.2.5]

- Minimize differences across all *-client source code

## [1.2.4]

- Support nested #foreach

## [1.2.3]

- Support #foreach dynamic loop directive

## [1.2.2]

- Support ${param} template variable and enforce ${param} in #if conditions

## [1.2.1]

- Collect queries in Client class and delete query_all.py

## [1.2.0]

- Support name referencing via `#include name` and `#include name(key)`

## [1.1.1]

- Refactoring code to apply ruff format, ruff check

## [1.0.0]

Initial release:

- MySQL helper using mysqlclient (MySQLdb)
- Connection pooling support
- YAML query management in tests/queries
- Conditional SQL with #if, #elif, #else, #endif
- Bilingual column aliases (en|ko)
- Streaming CSV export support
- Transaction handling via context manager
