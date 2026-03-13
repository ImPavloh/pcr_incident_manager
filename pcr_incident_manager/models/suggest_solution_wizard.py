# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class SuggestSolutionWizard(models.TransientModel):
    """
    Wizard para sugerir solución de incidencia usando IA.
    Analiza la descripción del problema y propone pasos
    de resolución que se pueden añadir al campo solución.
    """
    _name = 'pcr_incident_manager.suggest.solution.wizard'
    _description = 'Asistente de sugerencia de solución IA'

    incident_id = fields.Many2one('pcr_incident_manager.incident', string='Incidencia', readonly=True)
    incident_name = fields.Char(string='Problema', readonly=True)
    incident_description = fields.Text(string='Descripción', readonly=True)
    
    suggested_solution = fields.Text(string='Solución sugerida', readonly=True)
    remaining_requests = fields.Integer(string='Peticiones restantes hoy', readonly=True)
    
    state = fields.Selection([
        ('confirm', 'Confirmar'),
        ('success', 'Solución lista'),
        ('error', 'Error'),
    ], default='confirm')
    
    error_message = fields.Text(string='Mensaje de error', readonly=True)
    needs_config = fields.Boolean(default=False)
    
    # Validación
    has_enough_description = fields.Boolean(compute='_compute_validation')
    description_length = fields.Integer(compute='_compute_validation')

    @api.depends('incident_id')
    def _compute_validation(self):
        for wizard in self:
            desc = wizard.incident_id.description or ''
            wizard.description_length = len(desc)
            wizard.has_enough_description = len(desc.strip()) >= 20

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        incident_id = self._context.get('active_id')
        if incident_id:
            incident = self.env['pcr_incident_manager.incident'].browse(incident_id)
            res['incident_id'] = incident.id
            res['incident_name'] = incident.name
            res['incident_description'] = incident.description[:200] + '...' if incident.description and len(incident.description) > 200 else incident.description
            
            ai_service = self.env['pcr_incident_manager.ai.service']
            res['remaining_requests'] = ai_service._get_remaining_requests()
            res['state'] = 'confirm'
            
            if not ai_service._get_api_key():
                res['state'] = 'error'
                res['error_message'] = _('No hay clave API configurada')
                res['needs_config'] = True
        
        return res

    def action_confirm_analyze(self):
        self.ensure_one()
        
        # llamada al servicio de IA para que de una sugerencia de solución
        ai_service = self.env['pcr_incident_manager.ai.service']
        result = ai_service.suggest_solution(self.incident_id)
        
        self.remaining_requests = result.get('remaining', 0)
        
        if result.get('success'):
            self.state = 'success'
            self.suggested_solution = result['suggestion']
        else:
            self.state = 'error'
            self.error_message = result.get('error', 'Error desconocido')
            self.needs_config = result.get('needs_config', False)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pcr_incident_manager.suggest.solution.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply_solution(self):
        if self.incident_id and self.suggested_solution:
            current_solution = self.incident_id.solution or ''
            
            if current_solution:
                new_solution = current_solution + '\n\n--- Sugerencia IA ---\n' + self.suggested_solution
            else:
                new_solution = self.suggested_solution
            
            self.incident_id.write({'solution': new_solution})
            self.incident_id.message_post(
                body=f"Solución sugerida por IA añadida al campo de solución"
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Solución añadida'),
                    'message': _('La sugerencia de IA se ha añadido al campo de solución'),
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
