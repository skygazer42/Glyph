"""
Graph database for storing policy relationships.
"""

import os
import json
from typing import List, Dict, Any, Optional, Set
from neo4j import GraphDatabase
import networkx as nx

from ..agents.base.types import PolicyDocument


class KnowledgeGraph:
    """Knowledge graph for storing and querying policy relationships."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
        use_networkx: bool = True
    ):
        """Initialize the knowledge graph."""
        self.uri = uri
        self.user = user
        self.password = password
        self.use_networkx = use_networkx

        if use_networkx:
            self.graph = nx.DiGraph()
            self.driver = None
        else:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.graph = None

        self._init_graph()

    def _init_graph(self):
        """Initialize the graph structure."""
        if self.use_networkx:
            # NetworkX fallback
            self.graph = nx.DiGraph()
        else:
            # Neo4j initialization
            with self.driver.session() as session:
                session.run("""
                    CREATE CONSTRAINT IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE
                """)

    def add_policy_document(self, doc: PolicyDocument):
        """Add a policy document to the graph."""
        if self.use_networkx:
            self._add_policy_networkx(doc)
        else:
            self._add_policy_neo4j(doc)

    def _add_policy_networkx(self, doc: PolicyDocument):
        """Add policy using NetworkX."""
        # Add policy node
        self.graph.add_node(
            doc.id,
            title=doc.title,
            source=doc.source,
            doc_type=doc.doc_type,
            content=doc.content[:500],  # Store summary
            policy_type=doc.policy_type,
            publish_date=doc.publish_date
        )

        # Extract and add entities
        entities = self._extract_entities(doc)
        for entity in entities:
            entity_id = f"entity_{entity.lower().replace(' ', '_')}"
            self.graph.add_node(entity_id, name=entity, type="entity")
            self.graph.add_edge(doc.id, entity_id, relation="mentions")

        # Add department relationships
        if doc.relevant_departments:
            for dept in doc.relevant_departments:
                dept_id = f"dept_{dept.lower().replace(' ', '_')}"
                self.graph.add_node(dept_id, name=dept, type="department")
                self.graph.add_edge(doc.id, dept_id, relation="issued_by")

    def _add_policy_neo4j(self, doc: PolicyDocument):
        """Add policy using Neo4j."""
        with self.driver.session() as session:
            # Create policy node
            session.run("""
                MERGE (p:Policy {id: $id})
                SET p.title = $title,
                    p.source = $source,
                    p.doc_type = $doc_type,
                    p.content = $content,
                    p.policy_type = $policy_type,
                    p.publish_date = $publish_date
            """, **doc.__dict__)

            # Add entities and relationships
            entities = self._extract_entities(doc)
            for entity in entities:
                session.run("""
                    MATCH (p:Policy {id: $policy_id})
                    MERGE (e:Entity {name: $entity_name})
                    MERGE (p)-[:MENTIONS]->(e)
                """, policy_id=doc.id, entity_name=entity)

            # Add departments
            if doc.relevant_departments:
                for dept in doc.relevant_departments:
                    session.run("""
                        MATCH (p:Policy {id: $policy_id})
                        MERGE (d:Department {name: $dept_name})
                        MERGE (p)-[:ISSUED_BY]->(d)
                    """, policy_id=doc.id, dept_name=dept)

    async def find_related_policies(
        self,
        entity: str,
        max_depth: int = 2,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[PolicyDocument]:
        """Find policies related to an entity."""
        if self.use_networkx:
            return self._find_related_networkx(entity, max_depth, filters)
        else:
            return await self._find_related_neo4j(entity, max_depth, filters)

    def _find_related_networkx(
        self,
        entity: str,
        max_depth: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[PolicyDocument]:
        """Find related policies using NetworkX."""
        related_policies = []
        entity_id = f"entity_{entity.lower().replace(' ', '_')}"

        # Find policies connected to this entity
        if entity_id in self.graph:
            # Get all policies within max_depth
            for node in nx.single_source_shortest_path_length(
                self.graph, entity_id, cutoff=max_depth
            ).keys():
                if self.graph.nodes[node].get("type") != "entity":
                    node_data = self.graph.nodes[node]
                    if "title" in node_data:  # It's a policy
                        # Create PolicyDocument
                        doc = PolicyDocument(
                            id=node,
                            title=node_data.get("title", ""),
                            content=node_data.get("content", ""),
                            source=node_data.get("source", ""),
                            doc_type=node_data.get("doc_type", ""),
                            policy_type=node_data.get("policy_type", ""),
                            publish_date=node_data.get("publish_date")
                        )
                        if self._passes_filters(doc, filters):
                            related_policies.append(doc)

        return related_policies

    async def _find_related_neo4j(
        self,
        entity: str,
        max_depth: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[PolicyDocument]:
        """Find related policies using Neo4j."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {name: $entity})
                MATCH (p:Policy)-[*1..$max_depth]-(e)
                RETURN DISTINCT p
            """, entity=entity, max_depth=max_depth)

            policies = []
            for record in result:
                p = record["p"]
                doc = PolicyDocument(
                    id=p["id"],
                    title=p["title"],
                    content=p["content"],
                    source=p["source"],
                    doc_type=p["doc_type"],
                    policy_type=p["policy_type"],
                    publish_date=p["publish_date"]
                )
                if self._passes_filters(doc, filters):
                    policies.append(doc)

            return policies

    def _extract_entities(self, doc: PolicyDocument) -> List[str]:
        """Extract entities from document."""
        # Simple keyword extraction
        entities = []
        text = f"{doc.title} {doc.content}".lower()

        # Common policy entities
        policy_entities = [
            "补贴", "汽车", "家电", "消费券", "以旧换新",
            "济南市", "山东省", "商务厅", "财政局",
            "个人", "企业", "消费者", "居民"
        ]

        for entity in policy_entities:
            if entity in text:
                entities.append(entity)

        return entities

    def _passes_filters(self, doc: PolicyDocument, filters: Optional[Dict[str, Any]]) -> bool:
        """Check if document passes filters."""
        if not filters:
            return True
        # Implementation similar to vector store
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        if self.use_networkx:
            return {
                "total_nodes": self.graph.number_of_nodes(),
                "total_edges": self.graph.number_of_edges(),
                "policy_nodes": sum(1 for n in self.graph.nodes()
                                  if self.graph.nodes[n].get("title")),
                "entity_nodes": sum(1 for n in self.graph.nodes()
                                  if self.graph.nodes[n].get("type") == "entity"),
                "department_nodes": sum(1 for n in self.graph.nodes()
                                       if self.graph.nodes[n].get("type") == "department")
            }
        else:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (p:Policy) RETURN count(p) as policy_count
                """)
                policy_count = result.single()["policy_count"]

                result = session.run("""
                    MATCH (e:Entity) RETURN count(e) as entity_count
                """)
                entity_count = result.single()["entity_count"]

                return {
                    "policy_nodes": policy_count,
                    "entity_nodes": entity_count,
                    "total_nodes": policy_count + entity_count
                }