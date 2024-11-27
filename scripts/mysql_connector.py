import mysql.connector
from enum import Enum
import time


class ActionType(Enum):
    REMOVE = "Remove"
    MOVE_UP = "MoveUp"
    MOVE_DOWN = "MoveDown"
    SET_ORDER = "SetOrder"
    MOVE_TO_GROUP = "MoveToGroup"
    ADD_TO_GROUP = "AddToGroup"
    ADD_ORDER = "AddOrder"
    REMOVE_ORDER = "RemoveOrder"
    DISABLE = "Disable"
    ENABLE = "Enable"


class MySQLConnector:

    def __init__(self, database: str, user: str, password: str, host: str, port: str):
        self.driver = mysql.connector.connect(user=user, password=password, database=database, host=host,
                                              port=port, auth_plugin='mysql_native_password')

    # To construct vascular tree
    test_mode = True
    results = []

    def is_connected(self):
        return self.driver.is_connected()

    def query_lyphs(self):
        cursor = self.driver.cursor()
        cursor.execute('SELECT * FROM lyphs where isTemplate=1')
        col_names = cursor.column_names
        items = []
        for item in cursor:
            row = dict(zip(col_names, item))
            lyph = {"id": row.pop('ID'), "name": row.pop('label'), "ontologyTerms": row.pop('ontologyTerm')}
            items.append(lyph)
        cursor.close()
        return items

    def query_included(self):
        cursor = self.driver.cursor()
        query = """
            select distinct v.fma_id, v.name, COALESCE(t.include, 0) as include, t.lyph_template_ID from master_vascular_lyph_templates as t, 
            master_vascular_vessels as v where t.VESSEL_FMA_ID = v.fma_id order by v.name"""
        cursor.execute(query)
        nodes = []
        for item in cursor:
            obj = {"fmaID": str(item[0]), "name": item[1], "included": item[2],
                   "lyphTemplate": item[3] if item[3] else "---"}
            nodes.append(obj)
        return nodes

    # Get all vessels
    def query_vascular_nodes_map(self):
        cursor = self.driver.cursor()
        query = """SELECT node_id, fma_id, name, vessel_type, external FROM master_vascular_vessels"""
        cursor.execute(query)
        nodes = {}
        for item in cursor:
            obj = {"nodeID": str(item[0]), "fmaID": str(item[1]), "name": item[2],
                   "vesselType": str(item[3]), "external": item[3]}
            nodes[obj["nodeID"]] = obj
        return nodes

    # Create a new vessel
    def create_vessel(self, external_id, name, vessel_type):
        cursor = self.driver.cursor()
        query = """SELECT * FROM master_vascular_vessels where fma_id = %s"""
        cursor.execute(query, (external_id,))
        row = cursor.fetchone()
        if row is not None:
            return None
        query = """SELECT max(node_id) as max_id FROM master_vascular_vessels"""
        cursor.execute(query)
        next_id = None
        for value in cursor:
            next_id = value[0] + 1
        if not next_id:
            raise Exception("Failed to retrieve an ID for a new vessel!")
        # Create vessel
        query_add = """INSERT INTO master_vascular_vessels 
                            (node_id, fma_id, name, vessel_type, external) VALUES (%s, %s, %s, %s, %s)"""
        values = (next_id, external_id, name, vessel_type, 1)
        cursor.execute(query_add, values)
        # Create an  include record
        query_add = """INSERT INTO master_vascular_lyph_templates 
                            (VESSEL_FMA_ID, node_colour) VALUES (%s, %s)"""
        values = (external_id, 'orange')
        cursor.execute(query_add, values)
        self.driver.commit()
        return next_id

    # Get all edges to construct the vascular tree
    def query_vascular_edges(self):
        branches = []
        cursor = self.driver.cursor()
        query = """
            SELECT MAIN, BRANCH, CASE WHEN sequence = 0 THEN 1000 ELSE sequence END as sequence,
                vl1originalID, vl2originalID, 
                lyph_template_ID, node_colour, id, 
                vl1originalvesselname, vl2originalvesselname, disabled from (
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
                   'source_fma': str(item[3]), 'target_fma': str(item[4]),
                   'lyph_template': item[5], 'color': item[6], 'id': item[7],
                   'source_name': item[8], 'target_name': item[9], 'disabled': item[10]}
            branches.append(obj)
            prev = source
        for b in branches:
            if b["source"] == prev:
                b["total"] = count
        cursor.close()
        return branches

    # Edit the tree
    def execute_actions(self, entries, include, exclude, update):
        self.driver.autocommit = False
        self.update_include(include, exclude, update)
        res = ""
        for entry in entries:
            action_type = ActionType(entry["action"])
            params = entry["params"]
            try:
                if action_type == ActionType.REMOVE:
                    self.remove_edge(params)
                elif action_type == ActionType.MOVE_UP or action_type == ActionType.MOVE_DOWN:
                    self.move_up_or_down(params)
                elif action_type == ActionType.SET_ORDER:
                    self.update_order(params)
                elif action_type == ActionType.ADD_ORDER:
                    self.add_order(params)
                elif action_type == ActionType.REMOVE_ORDER:
                    self.remove_order(params)
                elif action_type == ActionType.MOVE_TO_GROUP:
                    self.move_to_group(params)
                elif action_type == ActionType.ADD_TO_GROUP:
                    self.add_to_group(params)
                elif action_type == ActionType.DISABLE or action_type == ActionType.ENABLE:
                    self.disable_enable(params)
            except Exception as e:
                res += "\nOperation failed: " + action_type
        self.driver.commit()
        return res

    def update_include(self, include, exclude, update):
        cursor = self.driver.cursor()
        if len(include) > 0:
            query1 = """update master_vascular_lyph_templates as v set v.include=1 where v.VESSEL_FMA_ID in ({0})""" \
                .format(','.join(f'"{w}"' for w in include))
            cursor.execute(query1)
        if len(exclude) > 0:
            query2 = """update master_vascular_lyph_templates as v set v.include=NULL where v.VESSEL_FMA_ID in ({0})""" \
                .format(','.join(f'"{w}"' for w in exclude))
            cursor.execute(query2)
        for key in update:
            self.update_template(key, update[key])

    def update_template(self, fma_id, lyph_template_id):
        cursor = self.driver.cursor()
        query = """update master_vascular_lyph_templates as v set v.lyph_template_ID=%s where v.VESSEL_FMA_ID='%s'"""
        values = (lyph_template_id, fma_id)
        cursor.execute(query, values)
        print("UPDATE, affected rows: ", cursor.rowcount)

    def query_versions(self):
        cursor = self.driver.cursor()
        query = """
            select id, user, date, description from master_vascular_logs order by date desc"""
        cursor.execute(query)
        versions = []
        for item in cursor:
            obj = {"id": item[0], "user": item[1], "date": str(item[2]), "description": item[3]}
            versions.append(obj)
        return versions

    def restore_from_backup(self, label, backup_current):
        label_new = time.strftime('%Y%m%d%H%M%S')
        now_backup = time.strftime('%Y-%m-%d %H:%M:%S')
        query1 = """CREATE TABLE master_vascular_lyph_templates_{0}_copy AS (SELECT * FROM master_vascular_lyph_templates_{0});""".format(label)
        query2 = """CREATE TABLE master_vascular_{0}_copy AS (SELECT * FROM master_vascular_{0});""".format(label)
        query = """RENAME TABLE 
            master_vascular TO master_vascular_{0}, 
            master_vascular_{1}_copy TO master_vascular, 
            master_vascular_lyph_templates TO master_vascular_lyph_templates_{0}, 
            master_vascular_lyph_templates_{1}_copy TO master_vascular_lyph_templates""".format(label_new, label)

        cursor = self.driver.cursor()
        cursor.execute(query1)
        cursor.execute(query2)
        cursor.execute(query)

        if backup_current:
            query_add = """INSERT INTO master_vascular_logs (id, user, date, description) VALUES (%s, %s, %s, %s)"""
            values = (label_new, "System", now_backup, "Auto-backup before restore " + label)
            cursor.execute(query_add, values)
        else:
            query_drop = """DROP TABLE master_vascular_{0}, master_vascular_lyph_templates_{0}""".format(label_new)
            cursor.execute(query_drop)

        self.driver.commit()

    def create_backup(self, user, comment):
        label = time.strftime('%Y%m%d%H%M%S')
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        values = (label, user, now, comment)
        query1 = """CREATE TABLE {0} AS (SELECT * FROM master_vascular_lyph_templates);""".format("master_vascular_lyph_templates_" + label)
        query2 = """CREATE TABLE {0} AS (SELECT * FROM master_vascular);""".format("master_vascular_" + label)
        query = """INSERT INTO master_vascular_logs (id, user, date, description) VALUES (%s, %s, %s, %s)"""
        cursor = self.driver.cursor()
        cursor.execute(query1)
        cursor.execute(query2)
        cursor.execute(query, values)
        self.driver.commit()
        return now

    # Remove edge from master_vascular (tested)
    def remove_edge(self, params):
        branch_id = params[0]["branch"]
        main = params[0]["source"].split('_')[0]
        sequence = params[0]["order"]
        query = """DELETE from master_vascular WHERE ID={0}""".format(branch_id)
        cursor = self.driver.cursor()
        cursor.execute(query)
        print("REMOVE, affected rows: ", cursor.rowcount)
        if sequence > 0:
            self.decrease_order(main, sequence)

    # Update edge order in master_vascular after removing one
    def decrease_order(self, main, start, end=None):
        query = """UPDATE master_vascular SET sequence = sequence - 1 WHERE MAIN={0} and sequence>{1}""".format(main, start)
        if end:
            query += """ and sequence<{0}""".format(end)
        cursor = self.driver.cursor()
        cursor.execute(query)
        print("ADJUST ORDER, affected rows: ", cursor.rowcount)

    # Update edge order in master_vascular after adding one
    def increase_order(self, main, start, end=None):
        query = """UPDATE master_vascular SET sequence = sequence + 1 WHERE MAIN={0} and sequence<{1}""".format(main, start)
        if end:
            query += """ and sequence>{0}""".format(end)
        cursor = self.driver.cursor()
        cursor.execute(query)
        print("ADJUST ORDER, affected rows: ", cursor.rowcount)

    # Swap order of two edges, TEST needed
    def move_up_or_down(self, params):
        branch_id1 = params[0]["branch"]
        sequence1 = params[0]["order"]
        branch_id2 = params[1]["branch"]
        sequence2 = params[1]["order"]
        if sequence1 < 0 or sequence2 < 0:
            raise Exception("Something wrong with sequences: " + sequence1 + ", " + sequence2)
        query1 = """UPDATE master_vascular SET sequence={0} WHERE ID={1}""".format(sequence1, branch_id1)
        cursor = self.driver.cursor()
        cursor.execute(query1)
        print("MOVE (1), affected rows: ", cursor.rowcount)
        query2 = """UPDATE master_vascular SET sequence={0} WHERE ID={1}""".format(sequence2, branch_id2)
        cursor.execute(query2)
        print("MOVE (2), affected rows: ", cursor.rowcount)

    # Place edge to another group - TEST needed
    def move_to_group(self, params):
        branch_id = params[0]["branch"]
        sequence = params[0]["order"]
        source = params[1]

        query = """UPDATE master_vascular SET main={0}, vl1originalID={1}, vl1originalvesselname="{2}", sequence={3} WHERE ID={4}""".\
            format(source["nodeID"], source["fmaID"], source["name"], sequence, branch_id)
        cursor = self.driver.cursor()
        cursor.execute(query)

        old_order = params[2]
        old_main = params[0]["source"].split('_')[0]
        print("MOVE-GROUP, affected rows: ", cursor.rowcount)
        self.decrease_order(old_main, old_order)

    # Add a new connection to the vascular network (tested)
    def add_to_group(self, params):
        source = params[0]
        target = params[1]
        order = params[2]
        cursor = self.driver.cursor()
        query = """SELECT max(id) as max_id FROM master_vascular"""
        cursor.execute(query)
        next_id = None
        for value in cursor:
            next_id = value[0] + 1
        if not next_id:
            raise Exception("Failed to retrieve an ID for a new record!")
        cursor = self.driver.cursor()
        query = """INSERT INTO master_vascular (
            ID, MAIN, vl1originalID, vl1originalvesselname, BRANCH, vl2originalID, vl2originalvesselname, vessel_type, sequence, disabled) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        values = (next_id, source["nodeID"], source["fmaID"], source["name"], target["nodeID"], target["fmaID"], target["name"], target["vesselType"], order, 0)
        cursor.execute(query, values)
        print("ADD-TO-GROUP: ", next_id)

    # Set disable flag
    def disable_enable(self, params):
        branch_id = params[0]["branch"]
        disabled = params[0]["disabled"]
        query = """UPDATE master_vascular SET disabled={0} WHERE ID={1}""" \
            .format(disabled, branch_id)
        cursor = self.driver.cursor()
        cursor.execute(query)
        print("ENABLE-DISABLE, affected rows: ", cursor.rowcount)

    # Add order to an unordered branch - TEST needed
    def add_order(self, params):
        branch_id = params[0]["branch"]
        sequence = params[0]["order"]
        query = """UPDATE master_vascular SET sequence={0} WHERE ID={1}""" \
            .format(sequence, branch_id)
        cursor = self.driver.cursor()
        cursor.execute(query)
        print("ADD-ORDER, affected rows: ", cursor.rowcount)

    # Remove the order - TEST needed
    def remove_order(self, params):
        branch_id = params[0]["branch"]
        query = """UPDATE master_vascular SET sequence=0 WHERE ID={0}""".format(branch_id)
        cursor = self.driver.cursor()
        cursor.execute(query)
        print("REMOVE-ORDER, affected rows: ", cursor.rowcount)
        # Adjust follow up orders
        main = params[0]["source"].split('_')[0]
        old_order = params[1]
        self.decrease_order(main, old_order)

    def update_order(self, params):
        branch_id = params[0]["branch"]
        order = params[0]["order"]
        # Adjust follow up orders
        main = params[0]["source"].split('_')[0]
        old_order = params[1]
        if old_order < order:
            self.decrease_order(main, old_order, order+1)
        else:
            self.increase_order(main, old_order, order-1)
        query = """UPDATE master_vascular SET sequence={0} WHERE ID={1}""".format(order, branch_id)
        cursor = self.driver.cursor()
        cursor.execute(query)
        print("SET-ORDER, affected rows: ", cursor.rowcount)

    # Delete duplicates from master_vascular
    # q = """select * from master_vascular as x where x.ID in (
    #     select SUBSTRING_INDEX(ids, ',', -1) AS redundant from (
    #     select v.vl1originalID, v.vl2originalID, GROUP_CONCAT(id) as ids, GROUP_CONCAT(sequence) as seqs from master_vascular as v
    #     group by v.vl1originalID, v.vl2originalID
    #     having count(*) > 1) as v1)
    #     order by x.vl1originalID, x.vl2originalID"""
    # Clean vessels list
    # """select * from master_vascular_vessels as y where y.node_id not in (
    # select distinct * from (
    # select v.main as node from master_vascular as v
    # union
    # select v.branch as node from master_vascular as v) as x) order by y.fma_id"""
    # select x.name, count(*) from master_vascular_vessels as x group by x.name having count(*) > 1