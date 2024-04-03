class Node(object):
    # generate new node
    def __init__(self, node_id):
        self.node_id = node_id
        self.children = []

    # append a child node to parent (self)
    def child(self, child_id):
        # check if child already exists in parent
        child_found = [c for c in self.children if c.node_id == child_id]
        if not child_found:
            # if it is a new child, create new node for this child
            _child = Node(child_id)
            # append new child node to parent's children list
            self.children.append(_child)
        else:
            # if the same, save this child
            _child = child_found[0]
        # return child object for later add
        return _child

    # convert the whole object to dict
    def as_dict(self):
        res = {'nodeID': self.node_id}
        res['children'] = [c.as_dict() for c in self.children]
        return res
