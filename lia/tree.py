from ldap3.utils.dn import parse_dn

class LdapNode:
    def __init__(self, name = None, data = None):
        self.name = name
        self.parent_node = None
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
        self._top = LdapNode()
        self._all = set()

    def add_node(self, path, data):
        node = self._top

        for name in reversed(path):
            node = node.get_child(name)

        if node.data:
            raise ValueError("Node not empty")
        else:
            node.data = data

    def __iter__(self):
        return iter(self._all)

    @staticmethod
    def _dn_to_path(dn):
        path = []
        rdn = []

        for component in parse_dn(dn):
            rdn.append(component[0] + "=" + component[1])

            if component[2] != "+":
                path.append( "+".join(sorted(rdn)) )
                rdn.clear()

        return path
