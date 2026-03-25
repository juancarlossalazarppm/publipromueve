"""
Acumula aprendizajes de un PR mergeado en publipromueve/projects/{repo}.md.
Debe ejecutarse con el workspace apuntando al repo publipromueve.
"""
import os
import anthropic
from github import Github
from datetime import datetime

repo_name = os.environ["REPO_NAME"]
repo_slug = os.environ["REPO_SLUG"]
pr_number = int(os.environ["PR_NUMBER"])
pr_title  = os.environ["PR_TITLE"]

gh   = Github(os.environ["GITHUB_TOKEN"])
repo = gh.get_repo(repo_name)
pr   = repo.get_pull(pr_number)

# Recopilar comentarios del PR (excluir los del bot de review)
review_comments = [
    f"[{c.user.login} en {c.path}]: {c.body[:400]}"
    for c in pr.get_review_comments()
][:25]

issue_comments = [
    f"[{c.user.login}]: {c.body[:400]}"
    for c in pr.get_issue_comments()
    if "AI Code Review" not in (c.body or "")
][:10]

all_comments = review_comments + issue_comments
if not all_comments:
    print("Sin comentarios de revision. Saltando acumulacion.")
    exit(0)

files_changed = [f.filename for f in pr.get_files()]

# Cargar historial actual del proyecto
history_file = f"projects/{repo_slug}.md"
os.makedirs("projects", exist_ok=True)

if os.path.exists(history_file):
    with open(history_file) as f:
        current_history = f.read()
else:
    current_history = (
        f"# Historial de aprendizajes: {repo_slug}\n\n"
        f"Este archivo acumula patrones, errores y decisiones detectadas en los PRs de {repo_slug}.\n"
    )

# Pedir a Claude que extraiga aprendizajes nuevos
client = anthropic.Anthropic()

prompt_lines = [
    "Analiza los comentarios de este PR mergeado y extrae aprendizajes valiosos para el proyecto.",
    "",
    f"PR #{pr_number}: {pr_title}",
    f"Archivos cambiados: {files_changed[:20]}",
    f"Descripcion: {(pr.body or '')[:500]}",
    "",
    "Comentarios del review:",
    "\n".join(all_comments),
    "",
    "Historial actual del proyecto (ultimas entradas):",
    current_history[-2000:],
    "",
    "Extrae SOLO aprendizajes nuevos que no esten ya en el historial.",
    "Responde UNICAMENTE en este formato (omite categorias sin contenido):",
    "PATRON: descripcion breve del patron de codigo recurrente detectado",
    "ERROR_COMUN: descripcion breve del error o antipatro que hay que evitar",
    "DECISION_ARQ: descripcion breve de la decision arquitectonica tomada",
    "ESTANDAR: descripcion breve del nuevo estandar o convencion acordada",
    "O si no hay nada nuevo: SIN_CAMBIOS",
]
prompt = "\n".join(prompt_lines)

message = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=800,
    messages=[{"role": "user", "content": prompt}]
)
learnings = message.content[0].text.strip()
print(f"Aprendizajes extraidos:\n{learnings}")

if "SIN_CAMBIOS" in learnings:
    print("Sin aprendizajes nuevos. Historial sin cambios.")
    exit(0)

# Agregar nueva seccion al historial
today = datetime.now().strftime("%Y-%m-%d")
new_section = f"\n## PR #{pr_number} - {today} | {pr_title[:60]}\n"

for line in learnings.split("\n"):
    line = line.strip()
    if not line or ":" not in line:
        continue
    category, _, text = line.partition(":")
    new_section += f"- **{category.strip()}**: {text.strip()}\n"

with open(history_file, "a") as f:
    f.write(new_section)

print(f"Historial actualizado: {history_file}")
