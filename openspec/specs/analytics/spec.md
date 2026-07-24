# Capability: analytics

Privacy-conscious, opt-in analytics for published `UserTemplate` pages. Code:
`apps/analytics/`, `static/analytics/`, and `templates/analytics/`.

## Requirement: Explicit public consent

The system SHALL render an analytics consent control only on a published public
template page (`GET /t/<slug>/`). It SHALL NOT create an analytics cookie or
persist an event before the visitor accepts. Declining SHALL remove the visitor
cookie and leave analytics persistence disabled for that browser.

### Scenario: No tracking before acceptance

- WHEN an anonymous visitor opens a published page for the first time
- THEN the consent banner is visible
- AND no `analytics_visitor_id` cookie or analytics event exists

### Scenario: Accept

- WHEN the visitor accepts analytics
- THEN the server sets a separate first-party pseudonymous visitor cookie
- AND the tracker may send bounded pageview, heartbeat, click, pointer-sample,
  and page-exit events

## Requirement: Bounded pseudonymous collection

The public consent and collect endpoints SHALL use no authentication identity,
accept JSON only, be CSRF-exempt because they are public, and be throttled.
The collector SHALL validate payload shape, event count, event kinds, safe target
descriptors, finite normalized coordinates in `[0,1]`, bounded duration and
viewport values, published template membership, and visitor/session ownership.
It SHALL not store IP addresses, raw user-agent values, query strings, form
values, or arbitrary href/selector data.

### Scenario: Invalid event

- WHEN a collector request contains an out-of-range, non-finite, malformed, or
  unsafe event value
- THEN it responds with a validation error
- AND it persists no event from that batch

### Scenario: Session duration

- WHEN a consented visitor sends a pageview followed by heartbeats or a page
  exit for a published template
- THEN one anonymous session records the bounded duration, event count, and
  safe exit descriptor

## Requirement: Owner-scoped reporting

The authenticated `/analytics/` dashboard SHALL expose only the current user's
template sessions and aggregates through `/api/analytics/`. It SHALL provide
period/template filters, visitor/session/pageview/click/duration metrics,
recent session behavior, and a heatmap based on normalized coordinates grouped
into a fixed 24x24 grid.

### Scenario: No cross-owner data

- WHEN a seller requests overview, sessions, or heatmap data
- THEN sessions belonging to another seller are excluded

## Requirement: Configurable retention

The `purge_analytics` management command SHALL delete sessions and cascaded
events older than the configured retention window and orphaned stale visitors.
`ANALYTICS_RETENTION_DAYS` SHALL default to 90 days and invalid non-positive
periods SHALL fail rather than silently use a different value.
