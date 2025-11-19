from rdflib import Graph, RDF, RDFS, OWL
from jinja2 import Environment, FileSystemLoader
import os

# Chargement de l'ontologie
g = Graph()
g.parse("ontology.rdf")

#Chargement des templates HTML
env = Environment(loader=FileSystemLoader("templates"))
index_template = env.get_template("index.html")
entity_template = env.get_template("entity.html")
class_template = env.get_template("class.html")
property_template = env.get_template("property.html")

# Création des dossiers de sortie
os.makedirs("wiki/entities", exist_ok=True)
os.makedirs("wiki/static", exist_ok=True)

# Copie manuelle du CSS 
os.system("cp static/style.css wiki/static/style.css")

def get_label(uri):
    label = g.value(uri, RDFS.label)
    return str(label) if label else uri.split("/")[-1]

def get_comment(uri):
    c = g.value(uri, RDFS.comment)
    return str(c) if c else ""

def make_file_name(uri):
    return get_label(uri) + ".html"

def make_html_file(entities,template,optional={}):
    for ent in entities:
        rels = []
        for p, o in g.predicate_objects(ent["uri"]):
            if not (p == RDF.type):
                rels.append((get_label(p), get_label(o)))
        html = template.render(
            label=ent["label"],
            uri=ent["uri"],
            comment=get_comment(ent["uri"]),
            types=[get_label(o) for o in g.objects(ent["uri"], RDF.type)],
            relations=rels,
            anti_rels=dic[ent["uri"]],
            individuals=optional
        )
        with open(f"wiki/entities/{ent['file']}", "w", encoding="utf-8") as f:
            if ent["uri"]: f.write(html)


entities = {
    "classes": [],
    "properties": [],
    "individuals": []
}

# Extraction des entités
for s, p, o in g.triples((None, RDF.type, OWL.Class)):
    if s.startswith("http://www.fates-mlops/"):
        entities["classes"].append({"uri": s, "label": get_label(s), "file": make_file_name(s)})

for s, p, o in g.triples((None, RDF.type, OWL.ObjectProperty)):
    if s.startswith("http://www.fates-mlops/"):
        entities["properties"].append({"uri": s, "label": get_label(s), "file": make_file_name(s)})

for s, p, o in g.triples((None, RDF.type, OWL.DatatypeProperty)):
    if s.startswith("http://www.fates-mlops/"):
        entities["properties"].append({"uri": s, "label": get_label(s), "file": make_file_name(s)})

# Tout ce qui n’est pas une classe ni propriété = individu
for s in set(g.subjects()) - {e["uri"] for cat in entities.values() for e in cat}:
    if s.startswith("http://www.fates-mlops/"):
        entities["individuals"].append({"uri": s, "label": get_label(s), "file": make_file_name(s)})

# Récupérations des listes d'instances par classe
class_dic = {}
for c in entities["classes"]:
    class_dic[c["uri"]] = []
    for s, p, o in g.triples((None, RDF.type, c["uri"])):
        if s.startswith("http://www.fates-mlops/"):
            class_dic[c["uri"]].append(get_label(s))

# Récupérations des listes de relations par type de relations
prop_dic = {}
for p in entities["properties"]:
    prop_dic[p["uri"]] = []
    for s, unused, o in g.triples((None, p["uri"], None)):
        if s.startswith("http://www.fates-mlops/") and o.startswith("http://www.fates-mlops/"):
            prop_dic[p["uri"]].append((get_label(s),get_label(o)))

# Récupération des relation inverses
dic = {}
for cat in entities.values():
    for ent in cat:
        dic[ent["uri"]] = []

for cat in entities.values():
    for ent in cat:
        for p, o in g.predicate_objects(ent["uri"]):
            if not (p == RDF.type):
                if o.startswith("http://www.fates-mlops/"):
                    dic[o].append((get_label(ent["uri"]), get_label(p)))


# Génération des pages d’entités
make_html_file(entities["classes"],class_template,class_dic)
make_html_file(entities["properties"],property_template,prop_dic)
make_html_file(entities["individuals"],entity_template)

# Page d'accueil
index_html = index_template.render(
    classes=entities["classes"],
    properties=entities["properties"],
    individuals=entities["individuals"]
)
with open("wiki/index.html", "w", encoding="utf-8") as f:
    f.write(index_html)

print("✅ Semantic wiki generated in ./wiki/")
