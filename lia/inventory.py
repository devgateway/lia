import logging, json

from .connection import ldap_connect

log = logging.getLogger(__name__)

_ldap = ldap_connect()

class Host:
    _by_name = {}
    _by_dn = {}

    @classmethod
    def get(cls, name = None, dn = None):
        """Factory to instantiate hosts or return loaded ones."""

        if name:
            try:
                host = cls._by_name[name]
            except KeyError:
                host = cls._find(name)
                cls._by_name[name] = host
                cls._by_dn[host._dn] = host
        elif dn:
            try:
                host = cls._by_dn[dn]
            except KeyError:
                host = cls._load(dn)
                cls._by_name[host.name] = host
                cls._by_dn[dn] = host
        else:
            raise ValueError("Either host name or DN required")

        return host

    @classmethod
    def _load(cls, dn):
        """Create Host instance from DN."""

        pass

    @classmethod
    def _find(cls, name):
        """Create Host instance from common name."""
        pass

    def __repr__(self):
        return json.dumps(self.vars, indent = 2)

class Inventory:

    def __init__(self):
        pass
