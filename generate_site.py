from owlready2 import * # type: ignore
from jinja2 import Environment, FileSystemLoader
import os
import re

ONTOLOGY_PATH = "ontology_filled.rdf"
PREFIX = "http://www.fates-mlops/"
OUTPUT = "wiki_mermaid_filled_final"

try:
    onto = get_ontology(ONTOLOGY_PATH).load() # type: ignore
except FileNotFoundError:
    print(f"Error: Could not find {ONTOLOGY_PATH}.")
    exit(1)

env = Environment(loader=FileSystemLoader("templates"))
try:
    index_template = env.get_template("index.html")
    entity_template = env.get_template("entity.html")
    class_template = env.get_template("class.html")
    property_template = env.get_template("property.html")
    viz_template = env.get_template("visualizations.html") # New template
except Exception as e:
    print(f"Template Error: {e}")
    exit(1)

os.makedirs(f"{OUTPUT}/entities", exist_ok=True)
os.makedirs(f"{OUTPUT}/static", exist_ok=True)
if os.path.exists("static/style.css"):
    os.system(f"cp static/style.css {OUTPUT}/static/style.css")


def safe_id(text):
    """Sanitizes strings for Mermaid Node IDs (alphanumeric only)."""
    return re.sub(r'[\W_]+', '', str(text))

def label(x):
    """Robust labeling."""
    if hasattr(x, "label") and x.label: return x.label[0]
    if hasattr(x, "name"): return x.name
    return str(x)

def comment(x):
    return str(x.comment[0]) if hasattr(x, "comment") and x.comment else ""

def write_entity_page(entity, template):
    """Writes individual HTML pages for entities."""
    fname = f"{safe_id(label(entity))}.html"
    
    html = template.render(
        label=label(entity),
        uri=entity.iri,
        comment=comment(entity),
        types=[label(t) for t in entity.is_a if not isinstance(t, (Restriction,Or,And))],
        relations=rels[entity],
        anti_rels=anti[entity],
        individuals= class_dic[entity] if entity in classes else (prop_dic[entity] if entity in properties else [])
    )
    with open(f"{OUTPUT}/entities/{fname}", "w", encoding="utf-8") as f:
        f.write(html)
    return fname



def generate_class_hierarchy_mermaid(classes):
    lines = ["graph TD"]
    lines.append('    %%{init: {"flowchart": {"padding": 20, "nodeSpacing": 50, "rankSpacing": 50}}}%%')
    lines.append('    classDef classNode fill:#ff6b35,stroke:#e55a2b,stroke-width:2px,color:#fff')
    lines.append('    classDef rootNode fill:#f7931e,stroke:#e55a2b,stroke-width:2px,color:#fff')
    
    lines.append('    Thing["owl:Thing"]:::rootNode')
    
    processed = set()
    
    def add_node(cls):
        if cls in processed: return
        processed.add(cls)
        
        node_id = safe_id(cls.name)
        lines.append(f'    {node_id}["{label(cls)}"]:::classNode')
        
        # Click event
        lines.append(f'    click {node_id} "entities/{node_id}.html" "Go to {label(cls)}"')
        
        # Parents
        parents = [p for p in cls.is_a if isinstance(p, ThingClass) and PREFIX in p.iri]
        if not parents:
             lines.append(f'    Thing --> {node_id}')
        else:
            for p in parents:
                p_id = safe_id(p.name)
                lines.append(f'    {p_id} --> {node_id}')
                add_node(p) 

    for c in classes:
        add_node(c)
        
    return "\n".join(lines)

def generate_property_graph_mermaid(classes, properties):
    # SWITCH TO GRAPH LR (Standard Flowchart)
    lines = ["graph BT"]
    
    # Increase spacing to make room for text labels
    lines.append('    %%{init: {"flowchart": {"nodeSpacing": 80, "rankSpacing": 100}}}%%')
    
    # Define the orange style for nodes
    lines.append('    classDef classNode fill:#ff6b35,stroke:#e55a2b,stroke-width:2px,color:#fff,font-weight:bold')

    added_rels = set()
    active_nodes = set()
    
    # --- Logic to find connections (Same as before) ---
    rels_to_draw = []
    
    # 1. Check Restrictions
    for cls in classes:
        for condition in cls.is_a:
            if isinstance(condition, Restriction):
                prop = condition.property
                target = condition.value
                if isinstance(target, ThingClass) and PREFIX in target.iri:
                    rels_to_draw.append((cls, target, prop))

    # 2. Check Domain/Range
    for prop in properties:
        domains = [d for d in prop.domain if isinstance(d, ThingClass) and PREFIX in d.iri]
        ranges = [r for r in prop.range if isinstance(r, ThingClass) and PREFIX in r.iri]
        for d in domains:
            for r in ranges:
                rels_to_draw.append((d, r, prop))

    # 3. Draw Edges
    for s, o, p in rels_to_draw:
        key = (s, o, p)
        if key not in added_rels:
            s_id = safe_id(s.name)
            o_id = safe_id(o.name)
            p_lbl = label(p)
            
            # Syntax change: double dash -- "Text" --> arrow
            lines.append(f'    {s_id} -- "{p_lbl}" --> {o_id}')
            
            active_nodes.add(s)
            active_nodes.add(o)
            added_rels.add(key)

    # Apply the orange style to all active nodes
    for node in active_nodes:
        n_id = safe_id(node.name)
        # Re-declare node with label to ensure styling works
        lines.append(f'    {n_id}["{label(node)}"]:::classNode')
        lines.append(f'    click {n_id} "entities/{n_id}.html"')

    if len(lines) == 3: # Only headers were added
        lines.append('    NoRelations["No properties found"]:::classNode')

    return "\n".join(lines)

def generate_instance_network_mermaid(individuals, properties):
    lines = ["graph LR"]
    
    # 1. INCREASE SPACING: Helps reduce line bunching
    # 'curve: basis' makes lines smoother
    lines.append('    %%{init: {"flowchart": {"nodeSpacing": 60, "rankSpacing": 120, "curve": "basis"}}}%%')
    
    lines.append('    classDef instanceNode fill:#ff6b35,stroke:#e55a2b,stroke-width:2px,color:#fff')
    lines.append('    classDef clusterLabel fill:#fff9f5,stroke:#f7931e,stroke-width:1px,color:#2d2d2d')
    
    # Data Gathering
    clusters = {}
    active_inds = set()
    connected_inds = set()
    edges_to_draw = []

    # Collect all valid edges first
    for prop in properties:
        for s, o in prop.get_relations():
            if s in individuals and o in individuals:
                connected_inds.add(s)
                connected_inds.add(o)
                edges_to_draw.append((s, prop, o))

    # Populate Clusters
    for ind in connected_inds:
        # Determine class/type for clustering
        types = [t for t in ind.is_a if isinstance(t, ThingClass) and PREFIX in t.iri]
        type_label = label(types[0]) if types else "Unclassified"
        
        if type_label not in clusters: clusters[type_label] = []
        clusters[type_label].append(ind)
        active_inds.add(ind)

    # 2. DRAW NODES (Sorted for consistent layout)
    for class_name, inds in clusters.items():
        safe_class = safe_id(class_name)
        lines.append(f'    subgraph {safe_class} ["{class_name}"]')
        lines.append(f'    direction TB') # Keep clusters vertical
        
        for ind in sorted(inds, key=lambda x: x.name):
            ind_id = safe_id(ind.name)
            lines.append(f'        {ind_id}["{label(ind)}"]:::instanceNode')
            lines.append(f'        click {ind_id} "entities/{ind_id}.html"')
            
        lines.append('    end')

    # 3. DRAW EDGES WITH COLOR CODING
    # Sort edges to ensure linkStyle indices align correctly every time
    edges_to_draw.sort(key=lambda x: (x[0].name, x[1].name, x[2].name))
    
    link_counter = 0
    link_styles = []

    for s, prop, o in edges_to_draw:
        if s in active_inds and o in active_inds:
            s_id = safe_id(s.name)
            o_id = safe_id(o.name)
            p_lbl = label(prop)
            p_name_lower = prop.name.lower()
            
            # Add the edge
            lines.append(f'    {s_id} -- "{p_lbl}" --> {o_id}')
            
            # Determine Style based on relationship name
            style = "stroke:#999,stroke-width:1px" # Default Gray
            
            if "negatively" in p_name_lower:
                # RED for Negative Impacts
                style = "stroke:#dc3545,stroke-width:2px"
            elif "positively" in p_name_lower:
                # GREEN for Positive Impacts
                style = "stroke:#28a745,stroke-width:2px"
            elif "refines" in p_name_lower:
                # BLUE DASHED for Hierarchy/Refines
                style = "stroke:#007bff,stroke-width:1px,stroke-dasharray: 5 5"            
            elif "evaluates" in p_name_lower:
                # PURPLE for Evaluates relationships
                style = "stroke:#6f42c1,stroke-width:2px"
            elif "ismeasuredby" in p_name_lower:
                # TEAL for Measurement relationships
                style = "stroke:#20c997,stroke-width:2px"
            elif "validfor" in p_name_lower:
                # ORANGE DASHED for ValidFor relationships
                style = "stroke:#fd7e14,stroke-width:2px,stroke-dasharray: 3 3"
            
            # Apply style to this specific link index
            link_styles.append(f'    linkStyle {link_counter} {style};')
            link_counter += 1

    # Append styles at the end
    lines.extend(link_styles)

    if not active_inds:
        lines.append('    Empty["No connected instances found"]')

    return "\n".join(lines)


classes = [c for c in onto.classes() if PREFIX in c.iri]
properties = [p for p in onto.object_properties() if PREFIX in p.iri]
individuals = [i for i in onto.individuals() if PREFIX in i.iri]

class_dic = {c: [label(i) for i in c.instances() if i.iri.startswith(PREFIX)] for c in classes}

rels = {ent: [] for ent in classes + properties + individuals}
anti = {ent: [] for ent in classes + properties + individuals}
prop_dic = {p: [] for p in properties}
for prop in properties:
    for s, o in prop.get_relations():
        prop_dic[prop].append((label(s), label(o)))
        rels[s].append((label(prop), label(o)))
        anti[o].append((label(s), label(prop)))


for c in classes:
    write_entity_page(c, class_template)
    
for p in properties:
    write_entity_page(p, property_template)
    
for i in individuals:
    write_entity_page(i, entity_template)



viz_html = viz_template.render(
    class_hierarchy=generate_class_hierarchy_mermaid(classes),
    property_graph=generate_property_graph_mermaid(classes, properties),
    instance_network=generate_instance_network_mermaid(individuals, properties)
)

with open(f"{OUTPUT}/visualizations.html", "w", encoding="utf-8") as f:
    f.write(viz_html)

index_html = index_template.render(
    title="FATES-MLOPS",
    classes=[{"label": label(c), "file": f"{safe_id(label(c))}.html"} for c in classes],
    properties=[{"label": label(p), "file": f"{safe_id(label(p))}.html"} for p in properties],
    individuals=[{"label": label(i), "file": f"{safe_id(label(i))}.html"} for i in individuals]
)
with open(f"{OUTPUT}/index.html", "w", encoding="utf-8") as f:
    f.write(index_html)
