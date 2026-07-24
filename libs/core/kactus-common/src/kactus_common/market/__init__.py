"""Market read-model contract, shared by the control plane and the data plane.

Only the *wire* contract lives here — enums, limits and response schemas. The
SQL that fills them is in ``kactus_data.market.service``, next to the DuckDB
tables it reads. Splitting it that way keeps kactus-common free of business
logic while giving both sides one definition to agree on, so the HTTP client in
kactus-fin cannot drift from the server in kactus-data-server.
"""
