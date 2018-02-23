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

* [Developing Dynamic Inventory
Sources](http://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html)

* [XDG Base Directory
Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-0.6.html)

# Configuration File

The JSON structure in this file defines how lia connects to LDAP server, and what information it
searches for.

## Dictionary Members

### `uri`

One or more space-delimited URIs of the LDAP server.

### `page`

Optional. Page size to request for search operations.

Default: 100.

### `cache_time`

Optional. Maximum age (in seconds) of the inventory cache at `$XDG_CACHE_HOME/lia.json` or
`~/.cache/lia.json`.

Default: 10800.

### `hosts`

A dictionary defining how to search for hosts and which attributes to request.

### `groups`

A list of dictionaries, each defining how to search for groups, which attributes to request, and
how to interpret host membership.

## Members of `hosts` Dictionary

### `base`

The node in LDAP, from which the search starts.

### `scope`

Optional. LDAP search scope, may only be *sub* for subtree search or any other value for base
search. This is a limitation imposed by the ldap3 library abstraction objects.

Default: sub.

### `objectclass`

A list of object class names to search for.

### `attr`

A dictionary describing attributes to request. The following members are
required.

#### `name`

The attribute containing host name (e.g. "cn").

If multiple values are returned for a single object (in other words, a host has multiple names),
lia will pick the one in common with the RDN components.

If none of the values are in the RDN, use the first alphabetically.

For example:

LDAP object:

    dn: cn=charlie,dc=example,dc=net
    cn: charlie
    cn: alpha

Host name: *charlie*

LDAP object:

    dn: vCPU=2+cn=bravo,dc=example,dc=net
    cn: bravo
    cn: alpha

Host name: *bravo*

LDAP object:

    dn: uuid=e035608b-cf04-4d2a-9451-0a7813c5225d,dc=example,dc=net
    cn: bravo
    cn: alpha

Host name: *alpha*

#### `var`

The attribute that holds JSON-formatted variables.

## Members of each element in `groups` list

### base, scope, objectclass

Group search criteria. See **Members of `hosts` Dictionary** above.

### `attr`

A dictionary describing attributes to request. The following members are
required:

#### `name`, `var`

Identical to the eponymous `hosts` members, see above.

#### `host`

The attribute listing member hosts.

#### `host_is_dn`

If *true*, then the attribute defined in *host* lists distinguished names of the member hosts.
Otherwise, it lists host names.

## Example Configuration

    {
      "uri": "ldaps://ldap.example.org",
      "page": 200,
      "cache_time": 86400,
      "hosts": {
        "base": "ou=hosts,dc=example,dc=org",
        "scope": "sub",
        "objectclass": ["ansibleHost", "device"],
        "attr": {
          "name": "cn",
          "var": "ansibleVars"
        }
      },
      "groups": [
        {
          "base": "ou=ansible,ou=groups,dc=example,dc=org",
          "scope": "sub",
          "objectclass": ["groupOfNames", "ansibleGroup"],
          "attr": {
            "name": "cn",
            "host": "member",
            "host_is_dn": true,
            "var": "ansibleVars"
          }
        },
        {
          "base": "ou=hosts,dc=example,dc=org",
          "scope": "sub",
          "objectclass": ["organizationalUnit", "ansibleGroup"],
          "attr": {
            "name": "ou",
            "var": "ansibleVars"
          }
        }
      ]
    }
