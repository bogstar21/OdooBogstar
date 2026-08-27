# -*- coding: utf-8 -*-
import base64
from datetime import date, datetime, time as dtime

from odoo import http
from odoo.http import request


class PortalCheckinController(http.Controller):
    """The worker-facing check-in page. `auth="public"` — no Odoo user account, no
    password, just the employee's unguessable `checkin_token` in the URL (see
    models/hr_employee.py). This is the Odoo-native replacement for the original
    StarX/holodBot Telegram bot / phone-only PWA: same "no login" worker experience,
    built as a plain Odoo controller instead of external infrastructure.
    """

    @http.route("/checkin/<string:token>", type="http", auth="public", website=False, csrf=True)
    def checkin_page(self, token, **kw):
        employee = request.env["hr.employee"].sudo().search([("checkin_token", "=", token)], limit=1)
        if not employee:
            return request.not_found()

        points = request.env["res.partner"].sudo().search([("field_worker_id", "=", employee.id)])
        recent = request.env["field.checkin"].sudo().search(
            [("worker_id", "=", employee.id)], order="checkin_at desc", limit=5
        )
        # The whole point of the Planner/Dispatch flow: the worker sees TODAY's route
        # on their own no-login page, with the same Google Maps link the admin sees
        # in the backend — without this, dispatching a route only ever reached the
        # admin's screen, never the person who actually has to drive it.
        today_plan = request.env["gps.route.plan"].sudo().search([
            ("worker_id", "=", employee.id), ("date", "=", date.today()),
        ], limit=1)
        # Which of today's route stops are already done — so the page can show them
        # crossed out instead of the worker having to remember/guess.
        today_checkins = request.env["field.checkin"].sudo().search([
            ("worker_id", "=", employee.id),
            ("checkin_at", ">=", datetime.combine(date.today(), dtime.min)),
            ("checkin_at", "<=", datetime.combine(date.today(), dtime.max)),
        ])
        done_point_ids = set(today_checkins.mapped("point_id").ids)

        return request.render("starx_gps.portal_checkin_page", {
            "employee": employee, "points": points, "recent": recent, "token": token,
            "plan": today_plan, "done_point_ids": done_point_ids,
            "submitted": kw.get("ok") == "1",
        })

    @http.route("/checkin/<string:token>/submit", type="http", auth="public", website=False,
                methods=["POST"], csrf=True)
    def checkin_submit(self, token, **post):
        employee = request.env["hr.employee"].sudo().search([("checkin_token", "=", token)], limit=1)
        if not employee:
            return request.not_found()

        point_id = int(post.get("point_id") or 0)
        try:
            lat = float(post.get("lat") or 0)
            lng = float(post.get("lng") or 0)
        except ValueError:
            lat = lng = 0.0

        if not point_id or not lat or not lng:
            # No GPS captured (denied permission, unsupported browser) or no stop
            # picked — send the worker back rather than silently dropping the visit.
            return request.redirect("/checkin/%s?ok=0" % token)

        vals = {
            "worker_id": employee.id, "point_id": point_id,
            "latitude": lat, "longitude": lng,
            "note": (post.get("note") or "")[:250],
        }
        photo = request.httprequest.files.get("photo")
        if photo and photo.filename:
            vals["photo"] = base64.b64encode(photo.read())

        # The signature pad sends a data-URI ("data:image/png;base64,....") in a
        # hidden field — Odoo's Binary field wants just the base64 payload, so the
        # "data:image/png;base64," prefix has to come off first. A blank/untouched
        # pad sends nothing (or just the prefix with no drawing), so this is optional.
        sig = (post.get("signature") or "").strip()
        if sig.startswith("data:image"):
            _, _, sig_b64 = sig.partition(",")
            if sig_b64:
                vals["signature"] = sig_b64

        request.env["field.checkin"].sudo().create(vals)
        return request.redirect("/checkin/%s?ok=1" % token)
