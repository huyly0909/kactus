"""One package per channel type — config schema, channel impl, event template.

Everything specific to a delivery target lives under ``channels/<type>/`` so
adding a channel is one new folder plus one line in each table in
:mod:`kactus_notification.registry`. The shared abstractions those packages
build on (``BaseChannelConfig``, ``BaseNotificationChannel``,
``BaseEventTemplate``) stay at the package root, which keeps the dependency
direction one-way: ``channels/*`` → root → ``const``, and ``registry`` →
``channels/*``.
"""
