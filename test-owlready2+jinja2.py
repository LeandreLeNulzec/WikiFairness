from owlready2 import * # type: ignore
from owlready2 import individual
from jinja2 import Environment, FileSystemLoader
import os

ONTOLOGY_PATH = "ontology.rdf"
PREFIX = "http://www.fates-mlops/"
OUTPUT = "wiki_owlready2"

# Chargement de l'ontologie
onto = get_ontology(ONTOLOGY_PATH).load() # type: ignore

#Chargement des templates HTML
env = Environment(loader=FileSystemLoader("templates"))
index_template = env.get_template("index.html")
entity_template = env.get_template("entity.html")
class_template = env.get_template("class.html")
property_template = env.get_template("property.html")

# Création des dossiers de sortie
os.makedirs(f"{OUTPUT}/entities", exist_ok=True)
os.makedirs(f"{OUTPUT}/static", exist_ok=True)
os.system(f"cp static/style.css {OUTPUT}/static/style.css")


def label(x):
    #  Classe OWL 
    if isinstance(x, ThingClass):
        return x.name

    # Propriété OWL 
    if isinstance(x, (ObjectPropertyClass, DataPropertyClass)):
        return x.name
    
    # individu OWL 
    if isinstance(x, Thing):
        return x.name

    # Restriction OWL 
    if isinstance(x, Restriction):
        prop = x.property.name
        filler = label(x.value)
        if x.type == SOME:
            return f"{prop} some {filler}"
        if x.type == ONLY:
            return f"{prop} only {filler}"
        if x.type == MIN:
            return f"{prop} min {x.cardinality} {filler}"
        if x.type == MAX:
            return f"{prop} max {x.cardinality} {filler}"
        if x.type == EXACTLY:
            return f"{prop} exactly {x.cardinality} {filler}"
        return f"{prop} ? {filler}"

    # Union / Intersection 
    if isinstance(x, Or):
        return " OR ".join(label(y) for y in x.Classes)
    if isinstance(x, And):
        return " AND ".join(label(y) for y in x.Classes)

    # fallback
    return str(x)

def comment(x):
    return str(x.comment[0]) if x.comment else ""


def filename(x):
    return f"{label(x)}.html"

def write_entity(e, template):
    print(e)
    html = template.render(
        label=label(e),
        uri=e.iri,
        comment=comment(e),
        types=[label(t) for t in e.is_a if not isinstance(t, (Restriction,Or,And))],
        relations=rels[e],
        anti_rels=anti[e],
        individuals= class_dic[e] if e in classes else (prop_dic[e] if e in properties else [])
    )
    with open(f"{OUTPUT}/entities/{filename(e)}", "w", encoding="utf-8") as f:
        f.write(html)


# Extraction des entités

classes = [c for c in onto.classes() if c.iri.startswith(PREFIX)]
obj_props = [p for p in onto.object_properties() if p.iri.startswith(PREFIX)]
#data_props = [p for p in onto.data_properties() if p.iri.startswith(PREFIX)]
properties = obj_props #+ data_props
individuals = [i for i in onto.individuals() if i.iri.startswith(PREFIX)]


class_dic = {c: [label(i) for i in c.instances() if i.iri.startswith(PREFIX)] for c in classes}

rels = {ent: [] for ent in classes + properties + individuals}
anti = {ent: [] for ent in classes + properties + individuals}
prop_dic = {p: [] for p in properties}
for prop in properties:
    for s, o in prop.get_relations():
        prop_dic[prop].append((label(s), label(o)))
        rels[s].append((label(prop), label(o)))
        anti[o].append((label(s), label(prop)))
print(prop_dic.keys() )
for c in classes:
    write_entity(c, class_template)

for p in properties:
    write_entity(p, property_template)

for i in individuals:
    write_entity(i, entity_template)



index_html = index_template.render(
    classes=[{"label": label(c), "file": filename(c)} for c in classes],
    properties=[{"label": label(p), "file": filename(p)} for p in properties],
    individuals=[{"label": label(i), "file": filename(i)} for i in individuals]
)
with open(f"{OUTPUT}/index.html", "w", encoding="utf-8") as f:
    f.write(index_html)