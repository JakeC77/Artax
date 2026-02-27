// ============================================
// Artax Knowledge Graph - Seed Data
// ============================================

// Clear existing data (for demos)
MATCH (n) DETACH DELETE n;

// ============ People ============

CREATE (jake:Person {
    name: "Jake",
    role: "Software Architect & Entrepreneur",
    location: "San Juan Island, WA",
    timezone: "US/Pacific",
    created: datetime()
})

CREATE (artax:Agent {
    name: "Artax",
    type: "AI Assistant",
    model: "Claude Opus",
    role: "Right Hand Man",
    created: datetime("2026-02-27T00:00:00Z")
})

// ============ Organizations ============

CREATE (geodesic:Organization {
    name: "Geodesic Works",
    type: "startup",
    domain: "Enterprise Knowledge Graphs",
    tagline: "The shortest path from operational complexity to executed action",
    stage: "building",
    website: "geodesicworks.com",
    created: datetime()
})

CREATE (islandtech:Organization {
    name: "Island AI and Tech",
    type: "consultancy",
    domain: "Local Tech Services",
    location: "San Juan Island, WA",
    stage: "concept",
    created: datetime()
})

// ============ Projects ============

CREATE (geodesic_platform:Project {
    name: "Geodesic Platform",
    status: "active",
    description: "Enterprise knowledge graph platform with agentic workflows",
    repo: "private",
    created: datetime()
})

CREATE (artax_kg:Project {
    name: "Artax Knowledge Graph",
    status: "active",
    description: "Personal KG backend for AI agent memory and reasoning",
    repo: "github.com/JakeC77/Artax",
    created: datetime()
})

CREATE (island_site:Project {
    name: "Island AI Website",
    status: "active",
    description: "Marketing site for San Juan Island tech consultancy",
    repo: "github.com/JakeC77/Artax",
    created: datetime()
})

// ============ Concepts ============

CREATE (kg:Concept {
    name: "Knowledge Graphs",
    domain: "technology",
    definition: "Graph-structured knowledge bases that represent entities and relationships",
    jake_perspective: "Core infrastructure for making AI agents actually useful"
})

CREATE (agents:Concept {
    name: "AI Agents",
    domain: "technology",
    definition: "Autonomous AI systems that can take actions on behalf of users",
    jake_perspective: "The future of human-computer interaction"
})

CREATE (entity_resolution:Concept {
    name: "Entity Resolution",
    domain: "technology",
    definition: "The process of determining when different references point to the same real-world entity",
    jake_perspective: "Critical for clean knowledge graphs"
})

CREATE (cypher:Concept {
    name: "Cypher",
    domain: "technology",
    definition: "Graph query language for Neo4j",
    jake_perspective: "Clean, expressive, good for agent integration"
})

// ============ Ideas ============

CREATE (kg_for_agents:Idea {
    title: "Knowledge Graph Backend for AI Agents",
    status: "exploring",
    source: "Artax",
    summary: "Use Geodesic to give AI agents structured memory and reasoning",
    created: datetime()
})

CREATE (island_practice:Idea {
    title: "San Juan Island Tech Practice",
    status: "exploring",
    source: "Jake",
    summary: "Local tech consultancy serving island businesses and residents",
    created: datetime()
})

// ============ Decisions ============

CREATE (decision_artax:Decision {
    summary: "Named AI assistant Artax",
    rationale: "Reference to The Neverending Story, but with a better fate",
    made_on: date("2026-02-27")
})

CREATE (decision_desandbox:Decision {
    summary: "De-sandboxed Artax for full system access",
    rationale: "Sandbox was causing more problems than it solved; droplet is isolated anyway",
    made_on: date("2026-02-27")
})

// ============ Relationships ============

// Jake's relationships
CREATE (jake)-[:FOUNDED]->(geodesic)
CREATE (jake)-[:WORKING_ON]->(geodesic_platform)
CREATE (jake)-[:WORKING_ON]->(artax_kg)
CREATE (jake)-[:WORKING_ON]->(island_site)
CREATE (jake)-[:INTERESTED_IN]->(kg)
CREATE (jake)-[:INTERESTED_IN]->(agents)
CREATE (jake)-[:INTERESTED_IN]->(entity_resolution)
CREATE (jake)-[:OWNS]->(artax)
CREATE (jake)-[:DECIDED]->(decision_artax)
CREATE (jake)-[:DECIDED]->(decision_desandbox)
CREATE (jake)-[:LIVES_IN]->(:Location {name: "San Juan Island", state: "WA", country: "USA"})

// Artax's relationships
CREATE (artax)-[:WORKS_FOR]->(jake)
CREATE (artax)-[:WORKING_ON]->(artax_kg)
CREATE (artax)-[:WORKING_ON]->(island_site)
CREATE (artax)-[:KNOWS_ABOUT]->(kg)
CREATE (artax)-[:KNOWS_ABOUT]->(agents)
CREATE (artax)-[:KNOWS_ABOUT]->(cypher)

// Organization relationships
CREATE (geodesic)-[:USES]->(kg)
CREATE (geodesic)-[:USES]->(cypher)
CREATE (geodesic)-[:BUILDING]->(geodesic_platform)
CREATE (islandtech)-[:LOCATED_IN]->(:Location {name: "Friday Harbor", island: "San Juan Island"})

// Project relationships
CREATE (geodesic_platform)-[:RELATES_TO]->(kg)
CREATE (geodesic_platform)-[:RELATES_TO]->(agents)
CREATE (artax_kg)-[:RELATES_TO]->(kg)
CREATE (artax_kg)-[:RELATES_TO]->(agents)
CREATE (artax_kg)-[:USES]->(cypher)

// Idea relationships
CREATE (kg_for_agents)-[:RELATES_TO]->(kg)
CREATE (kg_for_agents)-[:RELATES_TO]->(agents)
CREATE (kg_for_agents)-[:COULD_USE]->(geodesic_platform)
CREATE (island_practice)-[:MANIFESTS_AS]->(islandtech)
CREATE (island_practice)-[:MANIFESTS_AS]->(island_site)

// Concept relationships
CREATE (kg)-[:QUERIED_WITH]->(cypher)
CREATE (entity_resolution)-[:USED_IN]->(kg)
CREATE (agents)-[:ENHANCED_BY]->(kg)

// Return summary
MATCH (n) 
RETURN labels(n)[0] as type, count(*) as count
ORDER BY count DESC;
