# -*- coding: utf-8 -*-

from odoo import models, fields

class PcrEquipmentCategory(models.Model):
    """
    Categoría de equipos para clasificación y organización
    """
    _name = 'pcr_incident_manager.equipment_category'
    _description = 'Categoría de equipo'
    _inherit = ['product.category']
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    child_id = fields.One2many(
        'pcr_incident_manager.equipment_category',
        'parent_id',
        string='Subcategorías'
    )

    equipment_ids = fields.One2many(
        'pcr_incident_manager.equipment',
        'category_id',
        string='Equipos'
    )
    
    is_it_equipment = fields.Boolean(
        string='Equipo IT',
        default=True,
        help='Indica si es una categoría de equipos informáticos'
    )
    
    maintenance_frequency = fields.Selection([
        ('monthly', 'Mensual'),
        ('quarterly', 'Trimestral'),
        ('biannual', 'Semestral'),
        ('annual', 'Anual'),
    ], string='Frecuencia de mantenimiento')
