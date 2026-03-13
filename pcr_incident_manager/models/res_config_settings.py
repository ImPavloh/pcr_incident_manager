# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import requests

class ResConfigSettings(models.TransientModel):
    """Configuración del módulo: API key de IA y límites de uso."""
    _inherit = 'res.config.settings'

    # Configuración IA
    pcr_openrouter_api_key = fields.Char(
        string='Clave de OpenRouter',
        config_parameter='pcr_incident_manager.openrouter_api_key',
        help='Obtén tu clave gratis en https://openrouter.ai/keys'
    )
    pcr_ai_daily_limit = fields.Integer(
        string='Límite diario de peticiones',
        config_parameter='pcr_incident_manager.ai_daily_limit',
        default=50,
        help='Número máximo de peticiones a la IA por día'
    )
    pcr_ai_usage_today = fields.Integer(
        string='Peticiones usadas hoy',
        compute='_compute_ai_usage_today',
        readonly=True
    )
    
    # Configuración de modelos IA
    pcr_ai_model_mode = fields.Selection([
        ('auto', 'Automático (modelos gratuitos)'),
        ('custom', 'Modelo personalizado'),
    ], string='Modo de selección de modelo',
        config_parameter='pcr_incident_manager.ai_model_mode',
        default='auto',
        help='Automático usa modelos gratuitos con fallback. Personalizado permite elegir un modelo específico.'
    )
    
    pcr_ai_custom_model = fields.Char(
        string='Modelo personalizado',
        config_parameter='pcr_incident_manager.ai_custom_model',
        help='Nombre del modelo de OpenRouter (ej: openai/gpt-4o-mini, anthropic/claude-3-haiku). Consulta https://openrouter.ai/models'
    )
    
    pcr_ai_allow_paid = fields.Boolean(
        string='Permitir modelos de pago',
        config_parameter='pcr_incident_manager.ai_allow_paid',
        default=False,
        help='¡CUIDADO! Si activas esto y usas un modelo de pago, se cargará a tu cuenta de OpenRouter.'
    )
    
    pcr_mail_server_configured = fields.Boolean(
        string='Servidor de correo configurado',
        compute='_compute_mail_server_configured',
        readonly=True
    )

    @api.depends_context('uid')
    def _compute_mail_server_configured(self):
        """Verifica si hay al menos un servidor de correo saliente configurado"""
        mail_server = self.env['ir.mail_server'].sudo().search([], limit=1)
        for record in self:
            record.pcr_mail_server_configured = bool(mail_server)

    @api.depends_context('uid')
    def _compute_ai_usage_today(self):
        for record in self:
            record.pcr_ai_usage_today = int(
                self.env['ir.config_parameter'].sudo().get_param(
                    'pcr_incident_manager.ai_usage_count', '0'
                )
            )

    def action_reset_ai_usage(self):
        """Resetea el contador de peticiones IA del día a 0."""

        self.env['ir.config_parameter'].sudo().set_param('pcr_incident_manager.ai_usage_count', '0')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Contador reseteado'),
                'message': _('El contador de uso diario se ha puesto a 0'),
                'type': 'success',
            }
        }

    def action_test_ai_connection(self):
        """Prueba la conexión con la API de OpenRouter"""
        
        api_key = self.pcr_openrouter_api_key
        if not api_key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Escribe una clave primero'),
                    'type': 'danger',
                }
            }
        
        try:
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )

            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Conexión exitosa'),
                        'message': _('La clave es válida y la conexión funciona'),
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error de API'),
                        'message': _('La API devolvió error %s. Comprueba tu clave') % response.status_code,
                        'type': 'danger',
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error de conexión'),
                    'message': str(e),
                    'type': 'danger',
                }
            }
