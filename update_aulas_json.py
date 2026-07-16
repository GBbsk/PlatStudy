import json

with open('aulas.json', 'r') as f:
    aulas = json.load(f)

with open('node_aulas_fixed.json', 'r') as f:
    node_aulas = json.load(f)

for key, val in node_aulas.items():
    aulas[key] = val

with open('aulas.json', 'w') as f:
    json.dump(aulas, f, indent=2, ensure_ascii=False)
