# Runs the official Odoo image with our addon dropped into its extra-addons path.
# Railway builds this Dockerfile directly — same pattern as any other Railway deploy,
# just containerized because Odoo needs Python + the Odoo runtime + (via a separate
# Railway Postgres plugin) a database, not just a Node process.
FROM odoo:19.0

USER root
COPY ./starx_gps /mnt/extra-addons/starx_gps
COPY ./entrypoint.sh /entrypoint.sh
RUN chown -R odoo:odoo /mnt/extra-addons/starx_gps && chmod +x /entrypoint.sh
USER odoo

ENTRYPOINT ["/entrypoint.sh"]
