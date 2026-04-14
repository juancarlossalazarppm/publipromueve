"""
AI Code Review con contexto completo.
Carga: CLAUDE.md del repo + instrucciones del stack + historial del proyecto.
Configurado para igualar capacidades de CodeRabbit (perfil assertive).
"""
import os
import sys
import re
import fnmatch
import requests
import anthropic
from github import Github, Auth

# Validar que las variables requeridas existan
for var in ["ANTHROPIC_API_KEY", "GITHUB_TOKEN", "STACK", "REPO_NAME", "REPO_SLUG", "PR_NUMBER"]:
    if not os.environ.get(var):
        print(f"ERROR: Variable de entorno '{var}' no está configurada.")
        print(f"Verifica que el secret '{var}' exista en Settings → Secrets and variables → Actions")
        sys.exit(1)

stack     = os.environ["STACK"]
repo_name = os.environ["REPO_NAME"]
repo_slug = os.environ["REPO_SLUG"]
pr_number = int(os.environ["PR_NUMBER"])
base_url  = "https://raw.githubusercontent.com/juancarlossalazarppm/publipromueve/main"

# ============================================================================
# FILTRADO DE ARCHIVOS POR STACK (equivale a path_filters de CodeRabbit)
# ============================================================================
STACK_PATH_FILTERS = {
    "dotnet": {
        "include": ["src/**/*.cs", "**/*CommandHandler.cs", "**/*QueryHandler.cs",
                     "**/*Controller.cs", "**/*Validator.cs", "**/*Entity.cs", "**/*Repository.cs"],
        "exclude": ["**/bin/**", "**/obj/**", "**/*.csproj", "**/Migrations/**",
                     "**/*.Designer.cs", "**/wwwroot/**"],
    },
    "laravel": {
        "include": ["app/**/*.php", "routes/**/*.php", "database/**/*.php",
                     "config/**/*.php", "tests/**/*.php"],
        "exclude": ["vendor/**", "storage/**", "bootstrap/cache/**"],
    },
}

# Instrucciones por ruta (equivale a path_instructions de CodeRabbit)
DOTNET_PATH_INSTRUCTIONS = {
    "*.API/**/*.cs": (
        "CAPA API: Debe contener solo Controllers y configuración. "
        "NO debe tener lógica de negocio. Debe validar modelos con FluentValidation. "
        "Debe usar async/await correctamente. Debe manejar errores con ProcessResponse<T>."
    ),
    "*.Application/**/*.cs": (
        "CAPA APPLICATION: Debe seguir patrón CQRS (Commands/Queries separados). "
        "Handlers deben implementar IRequestHandler. NO debe referenciar Infrastructure directamente. "
        "Debe usar repositorios vía interfaces. Commands deben tener Validators correspondientes."
    ),
    "*.Domain/**/*.cs": (
        "CAPA DOMAIN: NO debe tener dependencias externas. "
        "Entidades deben heredar de BaseEntity<T>. Debe implementar validaciones de dominio. "
        "Debe seguir principios DDD."
    ),
    "*.Infrastructure/**/*.cs": (
        "CAPA INFRASTRUCTURE: Repositorios deben implementar interfaces de Application. "
        "Debe usar Unit of Work pattern. DbContext debe usar ReadDbContext/WriteDbContext. "
        "Debe aplicar configuraciones EF Core apropiadas."
    ),
    "*CommandHandler.cs": (
        "COMMAND HANDLER: Debe validar el Command con FluentValidation. "
        "Debe usar CancellationToken. Debe retornar ProcessResponse<T>. "
        "Debe aplicar transacciones cuando sea necesario."
    ),
    "*QueryHandler.cs": (
        "QUERY HANDLER: NO debe modificar estado. Debe usar .AsNoTracking() para consultas. "
        "Debe implementar paginación cuando sea apropiado. Debe usar read repositories."
    ),
}

LARAVEL_PATH_INSTRUCTIONS = {
    "app/Http/Controllers/**/*.php": (
        "CONTROLLER: Debe ser delgado, sin lógica de negocio. "
        "Usar Form Requests para validación. Retornar API Resources."
    ),
    "app/Models/**/*.php": (
        "MODEL: Usar $fillable explícito, nunca $guarded=[]. "
        "Definir relaciones y scopes. Usar UUIDs para IDs públicos."
    ),
    "app/Services/**/*.php": (
        "SERVICE: Contiene lógica de negocio. Debe ser inyectable. "
        "Usar interfaces para desacoplar."
    ),
}

STACK_PATH_INSTRUCTIONS = {
    "dotnet": DOTNET_PATH_INSTRUCTIONS,
    "laravel": LARAVEL_PATH_INSTRUCTIONS,
}

# Labels sugeridos por stack (equivale a labeling_instructions de CodeRabbit)
LABEL_DEFINITIONS = {
    "dotnet": [
        ("architecture", "Cambios que afectan la estructura de capas, CQRS, o patrones de diseño"),
        ("security", "Cambios relacionados con seguridad, autenticación, validación de datos"),
        ("performance", "Optimizaciones de performance, queries, async/await"),
        ("tests", "Adición o modificación de tests unitarios/integración"),
        ("bugfix", "Corrección de bugs identificados"),
        ("feature", "Nueva funcionalidad o endpoint"),
    ],
    "laravel": [
        ("architecture", "Cambios estructurales en el proyecto"),
        ("security", "Cambios de seguridad, autenticación, autorización"),
        ("performance", "Optimizaciones de queries, cache, N+1"),
        ("tests", "Tests unitarios o de integración"),
        ("bugfix", "Corrección de bugs"),
        ("feature", "Nueva funcionalidad"),
    ],
}


def matches_glob(filepath, pattern):
    """Verifica si un filepath coincide con un glob pattern."""
    if pattern.startswith("!"):
        return False
    # Convertir ** glob a regex simple
    regex = pattern.replace(".", r"\.").replace("**", ".*").replace("*", "[^/]*")
    return bool(re.search(regex, filepath))


def should_include_file(filepath, stack):
    """Determina si un archivo debe incluirse en el review según los filtros del stack."""
    filters = STACK_PATH_FILTERS.get(stack)
    if not filters:
        return True  # Sin filtros = incluir todo

    # Verificar exclusiones primero
    for pattern in filters.get("exclude", []):
        if matches_glob(filepath, pattern):
            return False

    # Verificar inclusiones
    for pattern in filters.get("include", []):
        if matches_glob(filepath, pattern):
            return True

    return False  # Si hay filtros de inclusión y no matcheó ninguno, excluir


def get_path_instructions(filepath, stack):
    """Obtiene instrucciones específicas según la ruta del archivo."""
    instructions = STACK_PATH_INSTRUCTIONS.get(stack, {})
    matched = []
    for pattern, instruction in instructions.items():
        if matches_glob(filepath, pattern):
            matched.append(instruction)
    return " | ".join(matched) if matched else ""


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

# 4. PR diff y metadata desde GitHub API (con filtrado de archivos)
gh   = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
repo = gh.get_repo(repo_name)
pr   = repo.get_pull(pr_number)

pr_files_text = []
skipped_files = []
total_additions = 0
total_deletions = 0

for f in pr.get_files():
    if not should_include_file(f.filename, stack):
        skipped_files.append(f.filename)
        continue

    total_additions += f.additions
    total_deletions += f.deletions
    patch = f.patch or "(binario o sin diff)"

    # Agregar instrucciones específicas por ruta si existen
    path_ctx = get_path_instructions(f.filename, stack)
    path_header = f"\n[Contexto de capa: {path_ctx}]" if path_ctx else ""

    pr_files_text.append(
        f"Archivo: {f.filename} (+{f.additions}/-{f.deletions}){path_header}\n```diff\n{patch[:2000]}\n```"
    )

pr_diff = "\n\n".join(pr_files_text[:20])

pr_base = pr.base.ref
pr_head = pr.head.ref
pr_body = pr.body or "Sin descripción"

# Obtener issues vinculados desde la descripción del PR
linked_issues = re.findall(r'(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)', pr_body, re.IGNORECASE)

linked_issues_text = ""
if linked_issues:
    issues_details = []
    for issue_num in linked_issues[:5]:
        try:
            issue = repo.get_issue(int(issue_num))
            issues_details.append(f"- #{issue_num}: {issue.title} (estado: {issue.state})")
        except Exception:
            issues_details.append(f"- #{issue_num}: (no se pudo obtener detalles)")
    linked_issues_text = "\n".join(issues_details)

# Definir labels disponibles para sugerencia
labels_text = ""
label_defs = LABEL_DEFINITIONS.get(stack, LABEL_DEFINITIONS.get("dotnet", []))
labels_text = "\n".join([f"- **{name}**: {desc}" for name, desc in label_defs])

# 5. Construir prompt con contexto completo (perfil assertive)
system_prompt = (
    "Eres un arquitecto de software senior que realiza code reviews EXHAUSTIVOS Y ASERTIVOS. "
    "Sé directo y profesional. Enfócate en Clean Architecture, CQRS, seguridad y performance. "
    "Valida separación de capas y patrones enterprise. "
    "No seas condescendiente: si algo está mal, dilo claramente con la corrección concreta. "
    "Si algo está bien, confírmalo brevemente y avanza. "
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
    f"Archivos cambiados: {pr.changed_files} (revisados: {len(pr_files_text)}, excluidos por filtro: {len(skipped_files)})",
    f"Lineas: +{total_additions}/-{total_deletions}",
    "",
]

# Agregar issues vinculados si existen
if linked_issues_text:
    sections.extend([
        "ISSUES VINCULADOS",
        linked_issues_text,
        "",
    ])

sections.extend([
    "CAMBIOS (archivos filtrados por relevancia)",
    pr_diff,
    "",
    "---",
    "Proporciona un code review detallado EN ESPAÑOL con TODAS estas secciones:",
    "",
    "## Resumen",
    "Resumen de alto nivel enfocado en:",
    "1. Cambios en arquitectura (capas, CQRS, patrones)",
    "2. Impacto en seguridad y performance",
    f"3. Cumplimiento de convenciones {stack}",
    "4. Calidad de tests y cobertura",
    "",
    "## Esfuerzo de Revisión",
    "Estima el esfuerzo necesario para revisar este PR manualmente:",
    "- Complejidad: Baja / Media / Alta",
    "- Tiempo estimado de revisión manual: X minutos",
    "- Riesgo de regresión: Bajo / Medio / Alto",
    "",
])

# Agregar evaluación de issues vinculados si existen
if linked_issues_text:
    sections.extend([
        "## Evaluación de Issues Vinculados",
        "Para cada issue vinculado, evalúa si los cambios del PR realmente resuelven el issue. "
        "Indica si la implementación es completa o parcial.",
        "",
    ])

sections.extend([
    "## Labels Sugeridos",
    f"Basándote en los cambios, sugiere uno o más labels de esta lista:\n{labels_text}",
    "Indica cuáles aplican y por qué.",
    "",
    "## Problemas Críticos",
    "Bugs, vulnerabilidades, violaciones de arquitectura. Si no hay: 'Ninguno detectado.'",
    "Para cada problema incluye: archivo, línea, descripción del problema, y corrección sugerida con código.",
    "",
    "## Advertencias",
    "Deuda técnica, patrones incorrectos, riesgos futuros.",
    "",
    "## Sugerencias de Mejora",
    "Con código corregido cuando aplique. Referencia archivo y línea.",
    "",
    "## Puntuación",
    "Score del 1 al 10 con justificación breve.",
    "",
    "INSTRUCCIONES FINALES:",
    "- Sé específico: referencia archivos y líneas concretas del diff.",
    "- Aplica los estándares del stack y los aprendizajes históricos.",
    "- Valida que cada archivo cumple las reglas de su capa (ver [Contexto de capa] en cada archivo).",
    "- Si detectas archivos que deberían tener tests y no los hay, menciónalo.",
    "- RECUERDA: Toda la respuesta debe estar en español.",
])
prompt = "\n".join(sections)

# 6. Llamar a Claude con contexto completo
client  = anthropic.Anthropic()
message = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=6000,
    system=system_prompt,
    messages=[{"role": "user", "content": prompt}]
)
review_text = message.content[0].text

# 7. Publicar como comentario en el PR
skipped_note = ""
if skipped_files:
    skipped_note = (
        f"\n<details><summary>Archivos excluidos del review ({len(skipped_files)})</summary>\n\n"
        + "\n".join([f"- `{f}`" for f in skipped_files[:20]])
        + ("\n- ..." if len(skipped_files) > 20 else "")
        + "\n</details>\n"
    )

footer = (
    f"{skipped_note}"
    "\n---\n"
    "*Revisión generada con contexto completo: CLAUDE.md + estándares de stack + historial del proyecto + instrucciones por capa*"
)
pr.create_issue_comment(f"## AI Code Review — {stack.upper()}\n\n{review_text}{footer}")
print(f"Review publicado exitosamente. Archivos revisados: {len(pr_files_text)}, excluidos: {len(skipped_files)}")
