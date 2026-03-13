# -*- coding: utf-8 -*-

from odoo import models, fields


class PcrTechnician(models.Model):
    """
    Técnicos que pueden ser asignados a incidencias.
    Puede vincularse a un usuario del sistema (res.users)
    para control de acceso basado en el técnico logueado.
    """
    _name = 'pcr_incident_manager.technician'
    _description = 'Técnico'

    # datos del técnico
    name = fields.Char(string='Nombre', required=True)
    specialty = fields.Char(string='Especialidad')
    user_id = fields.Many2one('res.users', string='Usuario del sistema')
    email = fields.Char(string='Correo electrónico')
    phone = fields.Char(string='Teléfono')
    image = fields.Image(string='Foto')
    
    # relacion one2many
    incident_ids = fields.One2many(
        'pcr_incident_manager.incident', 
        'technician_id', 
        string='Incidencias asignadas'
    )

    # validaciones para campos únicos (a nivel de base de datos)
    _sql_constraints = [
        ('email_unique', 'UNIQUE(email)', 'El correo ya está registrado para otro técnico'),
        ('user_unique', 'UNIQUE(user_id)', 'Este usuario ya está asignado a otro técnico'),
    ]
