import logging

from ldap3 import Connection

from .config import get_config

log = logging.getLogger(__name__)
_ldap = None

def ldap_connect():
    global _ldap

    if not _ldap:
        cfg = get_config()
        _ldap = Connection(
                server = cfg.uri,
                user = cfg.binddn,
                password = cfg.bindpw,
                raise_exceptions = True)
        _ldap.bind()

    return _ldap
