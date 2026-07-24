"""kactus-notification — the notification domain (channels, templates, delivery).

A **library**, not infrastructure: channel registry, template rendering, retry
policy and the 5-step Zalo QR login are all domain logic, which is why this no
longer sits in kactus-common (``CLAUDE.md``: kactus-common is infrastructure
only).  The move also keeps ``zlapi`` — unofficial and reverse-engineered — off
the dependency path of every package that merely imports a database session.

* ``const`` / ``schema`` / ``model``        — types, per-type config, neutral event, ORM channel.
* ``service``                               — ``NotificationChannelService`` (owner-scoped CRUD).
* ``channel`` / ``template`` / ``registry`` — channel I/O strategies + event templates + dispatch tables.
* ``dispatcher``                            — ``Notifier`` (render + deliver, blocking wrapped in ``to_thread``).
* ``config``                                — ``NotificationSettings`` mixin, merged in by the entry-point package.

kactus-fin adds only the HTTP layer (``kactus_fin.notification`` — API routes + app wiring).
A new channel type is a new enum value + one config schema + one channel + one
template — never a schema migration (gương ``AssetProvider``).
"""

# ORM model modules in this package — used by load_models() for Alembic autogenerate
MODELS: list[str] = [
    "kactus_notification.model",
]
