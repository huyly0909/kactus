"""Generic notification domain — channels (Telegram/Slack/…), config, events.

Shared infrastructure: the whole feature lives here so **any** downstream
package can send notifications (kactus-data crawl jobs, kactus-fin API):

* ``const`` / ``schema`` / ``model``        — types, per-type config, neutral event, ORM channel.
* ``service``                               — ``NotificationChannelService`` (owner-scoped CRUD).
* ``channel`` / ``template`` / ``registry`` — channel I/O strategies + event templates + dispatch tables.
* ``dispatcher``                            — ``Notifier`` (render + deliver, blocking wrapped in ``to_thread``).

kactus-fin adds only the HTTP layer (``kactus_fin.notification`` — API routes + app wiring).
A new channel type is a new enum value + one config schema + one channel + one
template — never a schema migration (gương ``AssetProvider``).
"""
