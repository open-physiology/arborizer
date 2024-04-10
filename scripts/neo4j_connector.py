# author: Natallia Kokash, natallia.kokash@gmail.com
from neo4j import GraphDatabase


class NEO4JConnector:

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def query_tree(self, source_fma, target_fma, session=None):
        if session is None:
            session = self.driver.session()
        cql_node = """
            MATCH p = (a:Structure {fmaID: $source})-[:Connects*]->(b:Structure {fmaID: $target}) with nodes(p) as path unwind path as m match (m)-[]->(n) return m,n
        """
        nodes = session.run(cql_node, source=source_fma, target=target_fma)
        db_items = [record for record in nodes.data()]
        res = []
        for entry in db_items:
            edge = {
                "source": entry["m"]["nodeID"] + ": " + entry["m"]["name"],
                "target": entry["n"]["nodeID"] + ": " + entry["n"]["name"]
            }
            res.append(edge)
        return res

    def query_path(self, source_fma, target_fma, session=None):
        if session is None:
            session = self.driver.session()
        cql_node = """MATCH p = (a: Structure {fmaID: $source})-[:Connects*]->(b: Structure {fmaID: $target}) return nodes(p) as m"""
        nodes = session.run(cql_node, source=source_fma, target=target_fma)
        db_items = [record for record in nodes.data()]
        res = []
        for entry in db_items:
            for node in entry["m"]:
                res.append(node["nodeID"] + ": " + node["name"])
        return res

    def query_fma(self, session=None):
        if session is None:
            session = self.driver.session()
        cql_node = """match (n:Structure) return n"""
        nodes = session.run(cql_node)
        db_items = [record for record in nodes.data()]
        res = []
        for entry in db_items:
            res.append({"fmaID": entry["n"]["fmaID"], "name": entry["n"]["name"]})
        return res

