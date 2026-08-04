# TODO

Ítems bloqueados por decisiones reales — ver `FYI.md`:

- [ ] Decidir cómo maneja `apps/accounts` el email (requerido en signup,
      opcional, o flujo de reset sin email) para poder construir el reset
      de contraseña
- [ ] Conseguir credenciales sandbox reales para verificar en vivo Stripe
      checkout hosteado, Bold, PayU/ePayco, y Mercado Pago

Decisiones de producto abiertas de `multi-html-bundle-upload` (feature #88
en `BACKLOG.csv`, contexto completo en `openspec/project.md`'s gotcha de
site bundle deploy) — implementado y verificado en vivo, pero estos 3
puntos quedaron sin resolver explícitamente en la propuesta:

- [ ] ¿Un bundle puede estar publicado en Vercel y maqueta-hosted al mismo
      tiempo? Hoy el código lo permite implícitamente (son flags
      independientes), nunca se confirmó como decisión de producto deliberada.
- [ ] `SiteBundle.entrypoint_path` queda fijo al momento de subir el bundle
      (sin endpoint para cambiarlo después) — decidir si hace falta poder
      editarlo sin re-subir todo el bundle.
- [ ] Sin cuota de ancho de banda/storage por seller en el serving
      maqueta-hosted (`GET /s/<slug>/<path>`) — solo hay throttle genérico
      por IP (120/min, `bundle_serve` scope), nada limita cuánto tráfico
      puede generar un solo bundle.

El estado del proyecto se mantiene en `BACKLOG.csv`; los contratos y
escenarios vigentes están en `openspec/`.
