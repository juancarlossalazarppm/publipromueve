"""
AI Code Review con contexto completo.
Carga: CLAUDE.md del repo + instrucciones del stack + historial del proyecto.
"""
import os
import requests
import anthropic
from github import Github

stack     = os.environ["STACK"]
repo_name = os.environ["REPO_NAME"]
repo_slug = os.environ["REPO_SLUG"]
pr_number = int(os.environ["PR_NUMBER"])
base_url  = "https://raw.githubusercontent.com/juancarlossalazarppm/publipromueve/main"

# 1. CLAUDE.md del repo actual (ya está en el workspace por actions/checkout)
claude_md = ""
if os.path.exists("CLAUDE.md"):
    with open("CLAUDE.md") as f:
        claude_md = f.read()[:4000]

# 2. Instrucciones del stack desde publipromueve
r = requests.get(f"{base_url}/.github/instructions/{stack}.md")
stack_instructions = r.text if r.status_code == 200 else "Sin instrucciones específicas para este stack."

# 3. Historial acumulado del proyecto
r = requests.get(f"{base_url}/projects/{repo_slug}.md")
project_history = r.text[:3000] if r.status_code == 200 else "Sin historial previo de este proyecto."

# 4. PR diff y metadata desde GitHub API
gh   = Github(os.environ["GITHUB_TOKEN"])
repo = gh.get_repo(repo_name)
pr   = repo.get_pull(pr_number)

pr_files_text = []
for f in pr.get_files():
    patch = f.patch or "(binario o sin diff)"
    pr_files_text.append(
        f"Archivo: {f.filename} (+{f.additions}/-{f.deletions})\n```diff\n{patch[:2000]}\n```"
    )
pr_diff = "\n\n".join(pr_files_text[:15])

pr_base = pr.base.ref
pr_head = pr.head.ref
pr_body = pr.body or "Sin descripción"

# 5. Construir prompt con contexto completo
system_prompt = (
    "Eres un arquitecto de software senior que realiza code reviews exhaustivos. "
    "REGLA OBLIGATORIA: TODA tu respuesta DEBE estar en español. "
    "Todos los títulos, descripciones, recomendaciones, comentarios de código y cualquier texto "
    "DEBEN estar escritos completamente en español. Nunca respondas en inglés."
)

sections = [
    "CONTEXTO DEL PROYECTO (CLAUDE.md)",
    claude_md if claude_md else "No disponible.",
    "",
    f"ESTANDARES DEL STACK ({stack})",
    stack_instructions,
    "",
    "APRENDIZAJES HISTORICOS DEL PROYECTO",
    project_history,
    "",
    f"PULL REQUEST #{pr_number}: {pr.title}",
    f"Descripcion: {pr_body[:1000]}",
    f"Base: {pr_base} <- {pr_head}",
    f"Archivos cambiados: {pr.changed_files}",
    "",
    "CAMBIOS",
    pr_diff,
    "",
    "---",
    "Proporciona un code review detallado EN ESPAÑOL con estas secciones:",
    "",
    "## Resumen",
    "Que hace este PR y su impacto en el proyecto.",
    "",
    "## Problemas Criticos",
    "Bugs, vulnerabilidades, violaciones de arquitectura. Si no hay: 'Ninguno detectado.'",
    "",
    "## Advertencias",
    "Deuda tecnica, patrones incorrectos, riesgos futuros.",
    "",
    "## Sugerencias de Mejora",
    "Con codigo corregido cuando aplique.",
    "",
    "## Puntuacion",
    "Score del 1 al 10 con justificacion breve.",
    "",
    "Se especifico: referencia archivos y lineas concretas. Aplica los estandares del stack y los aprendizajes historicos.",
    "RECUERDA: Toda la respuesta debe estar en español.",
]
prompt = "\n".join(sections)

# 6. Llamar a Claude Sonnet con contexto completo
client  = anthropic.Anthropic()
message = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=4000,
    system=system_prompt,
    messages=[{"role": "user", "content": prompt}]
)
review_text = message.content[0].text

# 7. Publicar como comentario en el PR
footer = (
    "\n\n---\n"
    "*Revision generada con contexto completo: CLAUDE.md + estandares de stack + historial del proyecto*"
)
pr.create_issue_comment(f"## AI Code Review — {stack.upper()}\n\n{review_text}{footer}")
print("Review publicado exitosamente.")
