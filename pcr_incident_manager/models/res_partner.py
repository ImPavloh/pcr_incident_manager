# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ResPartner(models.Model):
    """
    Extensión de contactos para vincular equipos e incidencias.
    Añade campos y acciones para ver equipos asignados
    y sus incidencias relacionadas.
    """
    _inherit = 'res.partner'

    # equipos asignados a este contacto/empresa
    equipment_ids = fields.One2many(
        'pcr_incident_manager.equipment',
        'partner_id',
        string='Equipos asignados'
    )

    # cantidad de equipos
    equipment_count = fields.Integer(
        string='Número de equipos',
        compute='_compute_equipment_count',
        store=True
    )

    # incidencias relacionadas con sus equipos
    incident_count = fields.Integer(
        string='Número de incidencias',
        compute='_compute_incident_count'
    )

    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        for record in self:
            record.equipment_count = len(record.equipment_ids)

    def _compute_incident_count(self):
        Incident = self.env['pcr_incident_manager.incident']
        for record in self:
            equipment_ids = record.equipment_ids.ids
            if equipment_ids:
                record.incident_count = Incident.search_count([
                    ('equipment_id', 'in', equipment_ids)
                ])
            else:
                record.incident_count = 0

    def action_view_equipment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Equipos',
            'res_model': 'pcr_incident_manager.equipment',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_incidents(self):
        self.ensure_one()
        equipment_ids = self.equipment_ids.ids

        if not equipment_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin equipos'),
                    'message': _('Este contacto no tiene equipos asignados. Añade un equipo para ver o registrar incidencias relacionadas.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Incidencias',
            'res_model': 'pcr_incident_manager.incident',
            'view_mode': 'tree,form',
            'domain': [('equipment_id', 'in', equipment_ids)],
        }
