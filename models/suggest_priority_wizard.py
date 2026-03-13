# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class SuggestPriorityWizard(models.TransientModel):
    """
    Wizard para sugerir prioridad de incidencia usando IA.
    Muestra la prioridad actual, permite solicitar análisis
    y aplicar la sugerencia al registro.
    """
    _name = 'pcr_incident_manager.suggest.priority.wizard'
    _description = 'Asistente de sugerencia de prioridad IA'

    incident_id = fields.Many2one('pcr_incident_manager.incident', string='Incidencia', readonly=True)
    current_priority = fields.Selection([
        ('0', 'Baja'),
        ('1', 'Normal'),
        ('2', 'Alta'),
        ('3', 'Urgente'),
    ], string='Prioridad actual', readonly=True)
    
    suggested_priority = fields.Selection([
        ('0', 'Baja'),
        ('1', 'Normal'),
        ('2', 'Alta'),
        ('3', 'Urgente'),
    ], string='Prioridad sugerida', readonly=True)
    
    reason = fields.Text(string='Razón de la sugerencia', readonly=True)
    remaining_requests = fields.Integer(string='Peticiones restantes hoy', readonly=True)
    
    state = fields.Selection([
        ('confirm', 'Confirmar'),
        ('loading', 'Analizando...'),
        ('success', 'Sugerencia lista'),
        ('error', 'Error'),
    ], default='confirm')
    
    error_message = fields.Text(string='Mensaje de error', readonly=True)
    warnings = fields.Text(string='Advertencias', readonly=True)
    needs_config = fields.Boolean(default=False)

    # Info para mostrar antes de confirmar
    incident_name = fields.Char(string='Incidencia (nombre)', readonly=True)
    has_description = fields.Boolean(compute='_compute_incident_info')
    has_equipment = fields.Boolean(compute='_compute_incident_info')
    has_types = fields.Boolean(compute='_compute_incident_info')
    readiness_score = fields.Integer(string='Calidad de datos', compute='_compute_incident_info')

    @api.depends('incident_id')
    def _compute_incident_info(self):
        for wizard in self:
            inc = wizard.incident_id
            wizard.has_description = bool(inc.description and len(inc.description.strip()) >= 10)
            wizard.has_equipment = bool(inc.equipment_id)
            wizard.has_types = bool(inc.type_ids)

            # puntuación de calidad porque la IA funciona mejor con buena info
            score = 0
            if wizard.has_description:
                score += 50
            if wizard.has_equipment:
                score += 25
            if wizard.has_types:
                score += 25
            wizard.readiness_score = score

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        incident_id = self._context.get('active_id')
        if incident_id:
            incident = self.env['pcr_incident_manager.incident'].browse(incident_id)
            res['incident_id'] = incident.id
            res['incident_name'] = incident.name
            res['current_priority'] = incident.priority
            
            # peticiones restantes
            ai_service = self.env['pcr_incident_manager.ai.service']
            res['remaining_requests'] = ai_service._get_remaining_requests()
            
            res['state'] = 'confirm'
            
            # verificar API
            if not ai_service._get_api_key():
                res['state'] = 'error'
                res['error_message'] = _('No hay clave de API configurada')
                res['needs_config'] = True
        
        return res

    def action_confirm_analyze(self):
        self.ensure_one()
        
        # ahora la IA analiza y sugiere una prioridad para esta incidencia
        ai_service = self.env['pcr_incident_manager.ai.service']
        result = ai_service.suggest_priority(self.incident_id)
        
        self.remaining_requests = result.get('remaining', 0)
        
        if result.get('success'):
            self.state = 'success'
            self.suggested_priority = result['priority']
            self.reason = result['reason']
            if result.get('warnings'):
                self.warnings = '\n'.join(result['warnings'])
        else:
            self.state = 'error'
            self.error_message = result.get('error', 'Error desconocido')
            self.needs_config = result.get('needs_config', False)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pcr_incident_manager.suggest.priority.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply_priority(self):
        if self.incident_id and self.suggested_priority:
            old_priority = dict(self._fields["current_priority"].selection).get(self.current_priority)
            new_priority = dict(self._fields["suggested_priority"].selection).get(self.suggested_priority)
            
            self.incident_id.write({'priority': self.suggested_priority})
            self.incident_id.message_post(
                body=f"Prioridad cambiada por IA: {old_priority} → {new_priority}<br/><em>{self.reason}</em>"
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Prioridad actualizada'),
                    'message': _('Prioridad cambiada a: %s') % new_priority,
                    'type': 'success',
                    'sticky': False,
                }
            }
        return {'type': 'ir.actions.act_window_close'}

    def action_open_settings(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.config.settings',
            'view_mode': 'form',
            'target': 'current',
            'context': {'module': 'pcr_incident_manager'},
        }

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
