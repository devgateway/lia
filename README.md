# lia - LDAP Inventory for Ansible

## Synopsis

    lia [-h] (--list|--host HOST)

## Description

Lia is a helper script to query hosts, groups, and variables from your LDAP server, and provide it
to [Ansible](https://www.ansible.com/). Lia is highly configurable to support caching and adjust to
any LDAP schema.

The program will cache the inventory in JSON format, and serve it until the cache expires.

## Options

### -h, --help

Show usage information, and exit.

### --list

Print all groups and variables.

### --host *HOST*

Print variables for the host *HOST*.

## Exit Status

Returns zero if the inventory was retrieved.

## Environment

### `LOG_LEVEL`

Sets verbosity of logging sent to standard error. Recognized levels are:

* `CRITICAL`
* `ERROR`
* `WARNING` (default)
* `INFO`
* `DEBUG`

## Files

### Configuration File

* `$XDG_CONFIG_HOME/lia.json`

* `~/.config/lia.json`

### Cached Inventory

* `$XDG_CACHE_HOME/lia.json`

* `~/.cache/lia.json`

## Conforming to

* [Developing Dynamic Inventory Sources](http://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html)

* [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-0.6.html)
