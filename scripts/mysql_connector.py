import mysql.connector


class MySQLConnector:

    def __init__(self, database: str, user: str, password: str, host: str, port: str):
        self.driver = mysql.connector.connect(user=user, password=password, database=database, host=host, port=port)

    def query_master_vascular_nodes_map(self):
        cursor = self.driver.cursor()
        query = """SELECT DISTINCT node_id, fma_id, name FROM 
            (SELECT MAIN_VESSEL as node_id, vl1originalID as fma_id, vl1originalvesselname as name FROM master_vascular mv
            UNION SELECT BRANCH as node_id, vl2originalID as fma_id, vl2originalvesselname AS fma_id FROM master_vascular mv) v"""
        cursor.execute(query)
        nodes = {}
        for item in cursor:
            obj = {"nodeID": str(item[0]), "fmaID": str(item[1]), "name": item[2]}
            nodes[obj["nodeID"]] = obj
        return nodes

    def query_master_vascular_edges(self):
        branches = []
        cursor = self.driver.cursor()
        query = """SELECT MAIN_VESSEL, BRANCH, vl2trunkname, vl2trunkID, vessel_type, sequence, vl1originalID, vl2originalID, lyph_template_ID, node_colour from (
                SELECT * FROM master_vascular WHERE MAIN_VESSEL in 
                (SELECT DISTINCT BRANCH FROM master_vascular, master_vascular_lyph_templates WHERE vl2originalID = VESSEL_FMA_ID and sequence > 0 and include) 				
                and sequence > 0) as v
                LEFT OUTER JOIN `master_vascular_lyph_templates` as lt ON v.vl2originalID = lt.VESSEL_FMA_ID  
                order by vl1originalID, MAIN_VESSEL, sequence
        """
        cursor.execute(query)
        prev = None
        count = 1
        for item in cursor:
            source = str(item[0])
            target = str(item[1])
            if source == prev:
                count += 1
            else:
                for b in branches:
                    if b["source"] == prev:
                        b["total"] = count
                count = 1
            obj = {"source": str(source), "target": str(target), "label": item[2], 'id': item[3], 'type': item[4],
                   'order': item[5], 'source_fma': str(item[6]), 'target_fma': str(item[7]), 'lyph_template': item[8], 'color': item[9]}
            branches.append(obj)
            prev = source
        for b in branches:
            if b["source"] == prev:
                b["total"] = count
        cursor.close()
        return branches

