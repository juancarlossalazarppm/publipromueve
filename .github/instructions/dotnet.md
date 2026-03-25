Revisa este PR siguiendo Clean Architecture con .NET 8. Valida:
- Separación de capas: Domain sin dependencias externas, Application solo con MediatR handlers y DTOs, Infrastructure con EF Core y repositorios, API con controllers delgados sin lógica de negocio.
- CQRS: Commands mutan estado, Queries solo leen. Los handlers no se llaman entre sí directamente.
- Autofac: el registro de servicios va en módulos (CommonModule, RepositoryModule, etc.), no en Program.cs.
- EF Core: usar read/write separation, evitar N+1 con Ardalis.Specification, no exponer DbContext fuera de Infrastructure.
- Eventos: domain events se procesan antes del SaveChanges; integration events via MassTransit (SQS/SNS) con patrón outbox si aplica.
- Logging: solo Serilog con structured logging, incluir tenantId y correlationId en el contexto.
- Seguridad: no exponer IDs internos, validar inputs en Application, autorización explícita en todos los endpoints.
Consulta el archivo CLAUDE.md del repo para contexto adicional de arquitectura.
