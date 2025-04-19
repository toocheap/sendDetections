# Changelog

## [Unreleased]

### Changed
- Simplified command-line interface structure by removing subcommands
- Default behavior is now to process files directly without requiring `submit` command
- Updated README and documentation to reflect new command structure
- Removed non-existent organizations API functionality

### Fixed
- Updated tests to work with new command structure
- Archived incompatible tests in `archived_tests` directory
- Cleaned up redundant comments and empty lines
- Removed debug log files
- Updated pytest configuration to exclude archived tests

### Removed
- Organization listing functionality (`--list-orgs` option)
- Subcommand structure (`submit`, `organizations` commands)
- Debug logging files

