Revisa este PR siguiendo Clean Architecture con .NET 8. Aplica un perfil ASERTIVO: sé directo, señala problemas sin rodeos, y exige cumplimiento estricto de los estándares.

## Separación de Capas (Validación Estricta)

### Capa Domain
- NO debe tener dependencias externas (ni NuGet, ni referencias a otros proyectos excepto shared kernel).
- Entidades deben heredar de BaseEntity<T>.
- Debe implementar validaciones de dominio dentro de las entidades.
- Debe seguir principios DDD: aggregates, value objects, domain events.
- NO debe contener DTOs, repositorios concretos, ni lógica de infraestructura.

### Capa Application
- Debe seguir patrón CQRS estricto: Commands mutan estado, Queries solo leen.
- Handlers deben implementar IRequestHandler<TRequest, TResponse>.
- Los handlers NO se llaman entre sí directamente.
- NO debe referenciar Infrastructure directamente (solo interfaces).
- Debe usar repositorios vía interfaces definidas en Application.
- Todo Command debe tener su Validator correspondiente con FluentValidation.
- Debe usar CancellationToken en todos los handlers.
- Debe retornar ProcessResponse<T> como tipo de respuesta estándar.

### Capa Infrastructure
- Repositorios deben implementar interfaces definidas en Application.
- Debe usar Unit of Work pattern.
- DbContext debe usar ReadDbContext/WriteDbContext (read/write separation).
- Debe aplicar configuraciones EF Core apropiadas (IEntityTypeConfiguration).
- No exponer DbContext fuera de Infrastructure.
- Evitar N+1 queries: usar Ardalis.Specification para query building.

### Capa API
- Controllers deben ser delgados: solo recibir request, despachar al mediator, retornar response.
- NO debe contener lógica de negocio.
- Debe validar modelos con FluentValidation (no DataAnnotations).
- Debe usar async/await correctamente en todos los endpoints.
- Debe manejar errores con ProcessResponse<T>.
- Autorización explícita en todos los endpoints.

## Patrones Específicos

### Command Handlers
- Debe validar el Command con FluentValidation antes de procesar.
- Debe usar CancellationToken.
- Debe retornar ProcessResponse<T>.
- Debe aplicar transacciones cuando sea necesario.
- Debe emitir domain events cuando corresponda.

### Query Handlers
- NO debe modificar estado bajo ninguna circunstancia.
- Debe usar .AsNoTracking() para todas las consultas.
- Debe implementar paginación cuando la respuesta puede ser grande.
- Debe usar read repositories (ReadDbContext).

### Validators (FluentValidation)
- Todo Command debe tener un Validator.
- Validaciones deben cubrir: campos requeridos, longitudes, formatos, rangos.
- Mensajes de validación deben ser descriptivos.

## Registro de Dependencias
- Autofac: el registro de servicios va en módulos (CommonModule, RepositoryModule, MediatorModule, etc.), NO en Program.cs.
- Verificar que nuevos servicios estén registrados en el módulo correcto.

## EF Core
- Usar read/write separation con ReadDbContext y WriteDbContext.
- Evitar N+1 con Ardalis.Specification.
- No exponer DbContext fuera de Infrastructure.
- Migrations deben ser coherentes con los cambios en entidades.

## Eventos
- Domain events se procesan antes del SaveChanges.
- Integration events via MassTransit (SQS/SNS) con patrón outbox si aplica.
- Verificar que los consumers de eventos estén registrados.

## Logging y Observabilidad
- Solo Serilog con structured logging.
- Incluir tenantId y correlationId en el contexto de logging.
- No usar Console.WriteLine ni Debug.WriteLine.

## Seguridad
- No exponer IDs internos (usar DTOs apropiados).
- Validar inputs en la capa Application (FluentValidation).
- Autorización explícita en todos los endpoints (no depender solo de autenticación).
- No hardcodear secrets ni connection strings.
- Verificar que no se expongan datos sensibles en logs o responses.

## Async/Await
- Todos los métodos de I/O deben ser async.
- No usar .Result o .Wait() (bloquea threads).
- Propagar CancellationToken en toda la cadena de llamadas.

Consulta el archivo CLAUDE.md del repo para contexto adicional de arquitectura.
