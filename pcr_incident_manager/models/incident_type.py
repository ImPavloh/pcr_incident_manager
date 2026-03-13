# -*- coding: utf-8 -*-

from odoo import models, fields

class PcrIncidentType(models.Model):
    """
    Tipos/categorías de incidencias
    Deja clasificar incidencias y definir nivel de impacto
    para ayudar en la priorización.
    """
    _name = 'pcr_incident_manager.incident.type'
    _description = 'Tipo de incidencia'
    name = fields.Char(string='Nombre', required=True)
    description = fields.Text(string='Descripción')

    impact_level = fields.Selection([
        ('low', 'Bajo'),
        ('medium', 'Medio'),
        ('high', 'Alto'),
        ('critical', 'Crítico'),
    ], string='Nivel de impacto', default='medium')
