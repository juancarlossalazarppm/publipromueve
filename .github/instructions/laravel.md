Revisa este PR siguiendo las best practices de Laravel 11. Valida:
- Arquitectura: controllers delgados que solo delegan a Services/Actions, repositorios para acceso a datos, Form Requests para toda validación de input.
- Eloquent: detectar N+1 queries (relaciones cargadas en loops sin with()), usar select() explícito, scopes reutilizables en el Model.
- Autorización: usar Policies y Gates, no verificaciones manuales de roles con strings.
- Jobs y colas: operaciones costosas (emails, reportes, notificaciones) siempre en Jobs con ShouldQueue, definir tries y backoff.
- API Resources: toda respuesta de API pasa por JsonResource, no retornar modelos Eloquent directamente, usar whenLoaded() para relaciones opcionales.
- Seguridad: no exponer IDs incrementales en URLs (usar UUID), usar $fillable en modelos, autenticación explícita en todas las rutas de API.
- Eventos: efectos secundarios (auditoría, notificaciones) en Listeners con ShouldQueue, no en el service principal.
Consulta el archivo CLAUDE.md del repo para contexto adicional de arquitectura.
