# Copyright 2017, Development Gateway, Inc.
# This file is part of lia, see COPYING.

import logging

from ldap3 import Connection

from .config import get_config, MissingConfigValue

_log = logging.getLogger(__name__)
_ldap = None

def ldap_connect():
    global _ldap

    if not _ldap:
        cfg = get_config()
        try:
            binddn = cfg.binddn
            bindpw = cfg.bindpw
        except MissingConfigValue:
            binddn = None
            bindpw = None

        _ldap = Connection(
                server = cfg.uri,
                user = binddn,
                password = bindpw,
                raise_exceptions = True)
        _ldap.bind()

    return _ldap
