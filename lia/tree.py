from ldap3.utils.dn import parse_dn

class NodeNotEmptyError(Exception):
    def __init__(self, path):
        self.dn = ",".join(reversed(path))

    def __str__(self):
        return "Node already added: " + self.dn

class LdapNode:
    def __init__(self, parent, name, data):
        self.name = name
        self.parent = parent
        self.child_nodes = set()
        self.data = data

    def get_child(self, name):
        for child in self.child_nodes:
            if child._name == name:
                return child

        child = __class__(name)
        self.child_nodes.add(child)
        child.parent = self
        return child

class LdapTree:
    def __init__(self):
        self._top = LdapNode(name = None, data = None)
        self._all = set()

    def add_node(self, dn, data):
        node = self._top

        for name in reversed(path):
            node = node.get_child(name)

        if node.data:
            raise NodeNotEmptyError(path)
        else:
            node.data = data

    def __iter__(self):
        return iter(self._all)

    @staticmethod
    def _dn_to_path(dn):
        """Split DN into top-down normalized node names."""

        path = []
        rdn = []

        for component in parse_dn(dn):
            rdn.append(component[0] + "=" + component[1])

            if component[2] != "+":
                path.append( "+".join(sorted(rdn)) )
                rdn.clear()

        return reversed(path)
