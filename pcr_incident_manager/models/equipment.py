# -*- coding: utf-8 -*-

from odoo import models, fields, api

class PcrEquipment(models.Model):
    """
    Catálogo de equipos/activos
    Permite registrar equipos, asociarlos a propietarios (res.partner)
    y hacer seguimiento de incidencias relacionadas.
    """
    _name = 'pcr_incident_manager.equipment'
    _description = 'Equipo / Activo'
    _order = 'name asc'

    # Campos básicos
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código interno')
    description = fields.Text(string='Descripción')
    image = fields.Image(string='Imagen')
    category = fields.Char(string='Categoría')
    
    # Relación con categoría de equipo
    category_id = fields.Many2one(
        'pcr_incident_manager.equipment_category',
        string='Categoría de equipo',
        help='Categoría del equipo'
    )

    state = fields.Selection([
        ('operative', 'Operativo'),
        ('broken', 'Averiado'),
        ('maintenance', 'En mantenimiento'),
    ], string='Estado', default='operative', required=True)

    # propietario/responsable del equipo (herencia de partner)
    partner_id = fields.Many2one(
        'res.partner',
        string='Propietario/responsable',
        help='Contacto o empresa responsable del equipo'
    )

    purchase_date = fields.Date(string='Fecha de adquisición')
    serial_number = fields.Char(string='Número de serie')

    # relacion one2many
    incident_ids = fields.One2many(
        'pcr_incident_manager.incident', 
        'equipment_id', 
        string='Incidencias'
    )

    # cantidad de incidencias
    incident_count = fields.Integer(
        string='Número de incidencias',
        compute='_compute_incident_count',
        store=True
    )

    # incidencias abiertas
    open_incident_count = fields.Integer(
        string='Incidencias abiertas',
        compute='_compute_open_incident_count',
        store=True
    )

    # validaciones
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'El código del equipo tiene que ser único'),
        ('serial_unique', 'UNIQUE(serial_number)', 'El número de serie tiene que ser único'),
    ]

    @api.depends('incident_ids')
    def _compute_incident_count(self):
        for record in self:
            record.incident_count = len(record.incident_ids)

    @api.depends('incident_ids.state')
    def _compute_open_incident_count(self):
        """Cuenta incidencias en estado 'open' o 'in_progress'."""
        
        for record in self:
            record.open_incident_count = len(record.incident_ids.filtered(
                lambda i: i.state in ['open', 'in_progress']
            ))
