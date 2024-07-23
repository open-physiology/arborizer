import mysql.connector


class MySQLConnector:

    def __init__(self, database: str, user: str, password: str, host: str, port: str):
        self.driver = mysql.connector.connect(user=user, password=password, database=database, host=host, port=port)

    # To construct vascular tree
    test_mode = True

    # Get all vessels
    def query_vascular_nodes_map(self):
        cursor = self.driver.cursor()
        query = """SELECT node_id, fma_id, name FROM master_vascular_vessels"""
        cursor.execute(query)
        nodes = {}
        for item in cursor:
            obj = {"nodeID": str(item[0]), "fmaID": str(item[1]), "name": item[2]}
            nodes[obj["nodeID"]] = obj
        return nodes

    # Get all vessels that are not in the tree
    def query_vascular_targets(self, edges):
        used_set = set()
        for edge in edges:
            used_set.add(edge["source"])
            used_set.add(edge["target"])
        cursor = self.driver.cursor()
        query = """SELECT node_id, fma_id, name FROM master_vascular_vessels"""
        cursor.execute(query)
        nodes = []
        for item in cursor:
            obj = {"nodeID": str(item[0]), "fmaID": str(item[1]), "name": item[2]}
            if obj["nodeID"] not in used_set:
                nodes.append(obj)
        return nodes

    # Get all edges to construct the vascular tree
    def query_vascular_edges(self):
        branches = []
        cursor = self.driver.cursor()
        query = """
            SELECT MAIN, BRANCH, CASE WHEN sequence = 0 THEN 1000 ELSE sequence END as sequence,
                vl1originalID, vl2originalID, lyph_template_ID, node_colour, id from (
                SELECT * FROM master_vascular WHERE MAIN in
                (SELECT DISTINCT BRANCH FROM master_vascular, master_vascular_lyph_templates WHERE vl2originalID = VESSEL_FMA_ID and include)) as v
                LEFT OUTER JOIN `master_vascular_lyph_templates` as lt ON v.vl1originalID = lt.VESSEL_FMA_ID
                order by vl1originalID, sequence
        """
        cursor.execute(query)
        prev = None
        count = 1
        for item in cursor:
            source = str(item[0])
            if source == prev:
                count += 1
            else:
                for b in branches:
                    if b["source"] == prev:
                        b["total"] = count
                count = 1
            obj = {"source": str(source), "target": str(item[1]), 'order': item[2],
                   'source_fma': str(item[3]), 'target_fma': str(item[4]), 'lyph_template': item[5], 'color': item[6],
                   'id': item[7]}
            branches.append(obj)
            prev = source
        for b in branches:
            if b["source"] == prev:
                b["total"] = count
        cursor.close()
        return branches

    # Edit the tree
    def execute_actions(self, entries):
        from enum import Enum

        class ActionType(Enum):
            REMOVE = "Remove"
            MOVE_UP = "MoveUp"
            MOVE_DOWN = "MoveDown"
            MOVE_TO_GROUP = "MoveToGroup"
            ADD_TO_GROUP = "AddToGroup"
            ADD_ORDER = "AddOrder"
            REMOVE_ORDER = "RemoveOrder"

        self.driver.autocommit = False
        for entry in entries:
            action_type = ActionType(entry["action"])
            params = entry["params"]
            if action_type == ActionType.REMOVE:
                self.remove_edge(params)
            elif action_type == ActionType.MOVE_UP or action_type == ActionType.MOVE_DOWN:
                self.change_order(params)
            elif action_type == ActionType.MOVE_TO_GROUP:
                self.move_to_group(params)
        self.driver.commit()

    # Remove edge from master_vascular, complete
    def remove_edge(self, params):
        branch_id = params[0]
        query = """DELETE from master_vascular WHERE ID={0}""".format(branch_id)
        cursor = self.driver.cursor()
        self.test_mode and print(query) or cursor.execute(query)
        print("REMOVE, affected rows: ", cursor.rowcount)
        self.decrease_order(params[0].main, params[0].sequence)

    # Update edge order in master_vascular after removing one, TEST needed
    def decrease_order(self, main, start):
        query = """UPDATE master_vascular SET sequence = sequence - 1 WHERE MAIN={0} and sequence>{1}""".format(main, start)
        cursor = self.driver.cursor()
        self.test_mode and print(query) or cursor.execute(query)
        print("ADJUST ORDER, affected rows: ", cursor.rowcount)

    # Swap order of two edges, TEST needed
    def change_order(self, params):
        branch_id1 = params[0]["branch"]
        sequence1 = params[0]["order"]
        branch_id2 = params[1]["branch"]
        sequence2 = params[1]["order"]
        if sequence1 < 0 or sequence2 < 0 or abs(sequence1-sequence2) != 1:
            print("Something wrong with sequences: ", sequence1, sequence2)
            return
        query = """UPDATE master_vascular SET sequence={0} WHERE ID={1}""".format(sequence1, branch_id1)
        cursor = self.driver.cursor()
        self.test_mode and print(query) or cursor.execute(query)
        print("MOVE-UP(1), affected rows: ", cursor.rowcount)
        query = """UPDATE master_vascular SET sequence={0} WHERE ID={1}""".format(sequence2, branch_id2)
        self.test_mode and print(query) or cursor.execute(query)
        print("MOVE-UP(2), affected rows: ", cursor.rowcount)

    # Place edge to another group - TEST
    def move_to_group(self, params):
        branch_id = params[0].branch
        sequence = params[0].order
        new_main = params[1]
        old_order = params[2]
        old_main = params[0].source.split('_')[0]
        print(branch_id, new_main)
        query = """UPDATE master_vascular SET main={0}, sequence={1} WHERE ID={2}""".format(new_main, sequence, branch_id)
        cursor = self.driver.cursor()
        self.test_mode and print(query) or cursor.execute(query)
        print("MOVE-GROUP, affected rows: ", cursor.rowcount)
        self.decrease_order(old_main, old_order)

    # Add order to an unordered branch - TEST
    def add_order(self, params):
        branch_id = params[0].branch
        sequence = params[0].order
        query = """UPDATE master_vascular SET sequence={0} WHERE ID={1}""" \
            .format(sequence, branch_id)
        cursor = self.driver.cursor()
        self.test_mode and print(query) or cursor.execute(query)
        print("ADD-ORDER, affected rows: ", cursor.rowcount)

    def remove_order(self, params):
        pass