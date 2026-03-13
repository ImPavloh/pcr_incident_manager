# -*- coding: utf-8 -*-

from odoo import models, fields, _
import requests
import json
import logging
import time

_logger = logging.getLogger(__name__)

# Lista de modelos gratuitos de openrouter ordenados por preferencia
# Si uno falla (404, 503...) se intenta el siguiente
DEFAULT_FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "google/gemma-3-4b-it:free",
    "mistral-small-3.1-24b-instruct:free",
    "qwen/qwen3-4b:free",
    "allenai/molmo-2-8b:free",
    "z-ai/glm-4.5-air:free"
]

# códigos de error que significa que debemos probar otro modelo
RETRY_STATUS_CODES = {404, 503, 502, 500, 529}

class PcrAIService(models.Model):
    """
    Servicio de integración con IA (OpenRouter)
    Proporciona sugerencias de prioridad y solución para incidencias
    usando modelos LLM. Con un control de uso diario y fallback de modelos.
    """
    _name = 'pcr_incident_manager.ai.service'
    _description = 'Servicio de IA para análisis de incidencias'

    name = fields.Char(string='Nombre', default='Servicio IA', required=True)
    active = fields.Boolean(string='Activo', default=True)


    # Métodos de configuración
    
    def _get_api_key(self):
        return self.env['ir.config_parameter'].sudo().get_param('pcr_incident_manager.openrouter_api_key', '')

    def _get_daily_limit(self):
        return int(self.env['ir.config_parameter'].sudo().get_param('pcr_incident_manager.ai_daily_limit', '50'))

    def _get_daily_usage(self):
        today = fields.Date.today()
        usage_date = self.env['ir.config_parameter'].sudo().get_param('pcr_incident_manager.ai_usage_date', '')
        count = int(self.env['ir.config_parameter'].sudo().get_param('pcr_incident_manager.ai_usage_count', '0'))
        
        if usage_date != str(today):
            self.env['ir.config_parameter'].sudo().set_param('pcr_incident_manager.ai_usage_date', str(today))
            self.env['ir.config_parameter'].sudo().set_param('pcr_incident_manager.ai_usage_count', '0')
            return 0
        return count

    def _increment_usage(self):
        count = self._get_daily_usage()
        self.env['ir.config_parameter'].sudo().set_param('pcr_incident_manager.ai_usage_count', str(count + 1))

    def _get_remaining_requests(self):
        """Calcula las peticiones restantes para hoy"""
        limit = self._get_daily_limit()
        usage = self._get_daily_usage()
        return max(0, limit - usage)

    def _get_model_mode(self):
        """Obtiene el modo de selección de modelo (auto/custom)"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'pcr_incident_manager.ai_model_mode', 'auto'
        )

    def _get_custom_model(self):
        """Obtiene el modelo personalizado configurado"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'pcr_incident_manager.ai_custom_model', ''
        )

    def _is_paid_allowed(self):
        """Verifica si se permiten modelos de pago"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'pcr_incident_manager.ai_allow_paid', 'False'
        ) == 'True'

    def _get_models_to_try(self):
        """
        Devolver lista de modelos a intentar según config
        El modo auto lista de modelos gratuitos con fallback
        El modo custom solo el modelo personalizado
        """
        mode = self._get_model_mode()
        
        if mode == 'custom':
            custom_model = self._get_custom_model()
            if custom_model:
                is_free = ':free' in custom_model.lower() or custom_model.endswith(':free')
                
                if not is_free and not self._is_paid_allowed():
                    _logger.warning(f"Modelo {custom_model} parece ser de pago pero no está permitido")
                    return []
                
                return [custom_model]
            
            else:
                _logger.warning("Modo custom pero sin modelo configurado, usando auto")
                return DEFAULT_FREE_MODELS
        
        return DEFAULT_FREE_MODELS

    def _get_last_request_time(self):
        """Obtiene el timestamp de la última petición para evitar rate limiting"""
        return float(self.env['ir.config_parameter'].sudo().get_param('pcr_incident_manager.ai_last_request_time', '0'))

    def _set_last_request_time(self):
        """Actualiza el timestamp de la última petición"""
        import time as time_module
        self.env['ir.config_parameter'].sudo().set_param('pcr_incident_manager.ai_last_request_time', str(time_module.time()))

    def _can_make_request(self):
        """Verifica si podemos hacer una petición (mínimo 2 segundos entre peticiones)"""
        import time as time_module
        last_time = self._get_last_request_time()
        current_time = time_module.time()
        return (current_time - last_time) >= 2

    def _validate_incident_for_ai(self, incident):
        issues = []
        
        if not incident.description or len(incident.description.strip()) < 10:
            issues.append(_('La descripción es muy corta o está vacía. Añade más detalles para un mejor análisis.'))
        
        if not incident.equipment_id and not incident.type_ids:
            issues.append(_('No hay equipo ni tipos asignados. Añade contexto para mejor precisión.'))
        
        return issues

    def _call_openrouter(self, prompt, max_tokens=200):
        """
        Realiza petición HTTP a la api de OpenRouter con sistema de fallback.
        Intenta múltiples modelos si uno falla (404, 503, etc.)
        
        Docs:
        https://openrouter.ai/docs/quickstart
        https://openrouter.ai/docs/faq#how-are-rate-limits-calculated

        Returns dict con 'success', 'content'/'error', 'remaining'.
        """
        api_key = self._get_api_key()
        
        if not api_key:
            return {
                'success': False,
                'error': _('Clave no configurada. Ve a Incidencias > Configuración > Ajustes IA'),
                'needs_config': True
            }
        
        remaining = self._get_remaining_requests()
        if remaining <= 0:
            return {
                'success': False,
                'error': _('Límite diario alcanzado (%s peticiones). Intenta mañana o aumenta el límite en configuración.') % self._get_daily_limit(),
                'remaining': 0
            }

        # Verificar rate limiting entre peticiones
        if not self._can_make_request():
            return {
                'success': False,
                'error': _('Espera 2 segundos entre peticiones para evitar límites de tasa.'),
                'remaining': remaining
            }

        # Obtener modelos a intentar según config
        models_to_try = self._get_models_to_try()
        
        if not models_to_try:
            return {
                'success': False,
                'error': _('No hay modelos configurados. Si usas modo personalizado, configura un modelo o activa "Permitir modelos de pago".'),
                'remaining': remaining,
                'needs_config': True
            }

        last_error = None
        models_tried = []
        
        for i, model in enumerate(models_to_try):
            models_tried.append(model.split('/')[-1].split(':')[0])
            
            # Pequeño delay entre modelos para evitar rate limiting (excepto el primero)
            # ya que pueden ser peticiones rápidas en bucle (y causar 429)
            if i > 0:
                time.sleep(1)
            
            try:
            # llamada HTTP a OpenRouter
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://odoo.local",
                        "X-Title": "PCR Incident Manager"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_tokens,
                        "temperature": 0.3
                    },
                    timeout=30
                )
                
                if response.status_code in RETRY_STATUS_CODES:
                    _logger.warning(f"Modelo {model} no disponible (HTTP {response.status_code}), probando siguiente...")
                    last_error = _('Modelo %s no disponible') % model.split('/')[-1]
                    continue
                
                if response.status_code == 429:
                    # verificar si se puede continuar con otro modelo
                    remaining_today = self._get_remaining_requests()
                    if remaining_today <= 0:
                        return {
                            'success': False,
                            'error': _('Límite diario de peticiones alcanzado (%s). Intenta mañana o aumenta el límite en configuración.') % self._get_daily_limit(),
                            'remaining': 0
                        }
                    else:
                        _logger.warning(f"Rate limit con {model}, esperando 3 segundos y probando siguiente modelo...")
                        time.sleep(3)
                        last_error = _('Límite de tasa temporal')
                        continue
                
                if response.status_code != 200:
                    _logger.error(f"OpenRouter error con {model}: {response.status_code} - {response.text}")
                    last_error = _('Error de API (%s)') % response.status_code
                    continue

                data = response.json()
                
                if 'error' in data:
                    error_msg = data['error'].get('message', str(data['error']))
                    _logger.warning(f"Error de modelo {model}: {error_msg}")
                    last_error = error_msg
                    continue
                
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                if not content or not content.strip():
                    _logger.warning(f"Respuesta vacía del modelo {model}, probando siguiente...")
                    last_error = _('Respuesta vacía del modelo')
                    continue
                
                self._increment_usage()
                self._set_last_request_time()
                _logger.info(f"Respuesta exitosa del modelo: {model}")
                
                return {
                    'success': True,
                    'content': content.strip(),
                    'remaining': remaining - 1,
                    'model_used': model
                }
                    
            except requests.exceptions.Timeout:
                _logger.warning(f"Timeout con modelo {model}, probando siguiente...")
                last_error = _('Timeout con %s') % model.split('/')[-1]
                continue
            
            except requests.exceptions.RequestException as e:
                _logger.error(f"Error de conexión con {model}: {e}")
                last_error = _('Error de conexión')
                continue
        
        # ingún modelo funcionó (se muestra último error y ya, nada más que se pueda hacer)
        _logger.error(f"Todos los modelos fallaron. Probados: {', '.join(models_tried)}")
        return {
            'success': False,
            'error': _('Ningún modelo IA disponible. Último error: %s') % last_error,
            'remaining': remaining,
            'models_tried': models_tried
        }


    # Métodos públicos de sugerencia
    
    def suggest_priority(self, incident):
        """Analiza incidencia y sugiere prioridad (0-3) con justificación"""
        issues = self._validate_incident_for_ai(incident)
        context_parts = [f"Título: {incident.name}"]
        
        if incident.description:
            context_parts.append(f"Descripción: {incident.description[:500]}")
        
        if incident.equipment_id:
            eq = incident.equipment_id
            context_parts.append(f"Equipo: {eq.name} ({eq.category or 'sin categoría'})")
        
        if incident.type_ids:
            types_with_impact = []
            for t in incident.type_ids:
                impact = dict(t._fields['impact_level'].selection).get(t.impact_level, 'medio')
                types_with_impact.append(f"{t.name} (impacto {impact})")
            context_parts.append(f"Tipos: {', '.join(types_with_impact)}")

        # prompt para la IA con toda la info de la incidencia
        prompt = f"""Analiza esta incidencia IT y sugiere prioridad.

{chr(10).join(context_parts)}

Prioridades: 0=Baja, 1=Normal, 2=Alta, 3=Urgente

Responde SOLO JSON: {{"priority": 0-3, "reason": "explicación corta"}}"""

        result = self._call_openrouter(prompt, max_tokens=100)
        
        if not result['success']:
            return {**result, 'warnings': issues}
        
        try:
            content = result['content'].strip()
            if not content:
                return {
                    'success': False,
                    'error': _('La IA devolvió una respuesta vacía. Intenta de nuevo.'),
                    'remaining': result['remaining'],
                    'warnings': issues
                }

            if '```' in content:
                parts = content.split('```')
                content = parts[1] if len(parts) > 1 else parts[0]
                content = content.replace('json', '', 1).strip()

            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and end > start:
                content = content[start:end+1]
            else:
                # si no hay JSON válido intentar extraer la prioridad del texto
                _logger.warning(f"No se encontró JSON en respuesta: {result['content'][:100]}")
                return {
                    'success': False,
                    'error': _('Formato de respuesta inesperado. Intenta de nuevo.'),
                    'remaining': result['remaining'],
                    'warnings': issues
                }

            parsed = json.loads(content)
            priority = max(0, min(3, int(parsed.get('priority', 1))))
            
            return {
                'success': True,
                'priority': str(priority),
                'priority_label': ['Baja', 'Normal', 'Alta', 'Urgente'][priority],
                'reason': parsed.get('reason', 'Análisis completado')[:200],
                'remaining': result['remaining'],
                'warnings': issues
            }
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            _logger.warning(f"AI response parse error: {result['content']} - {e}")
            return {
                'success': False,
                'error': _('Respuesta de IA no válida. Intenta de nuevo.'),
                'remaining': result['remaining'],
                'warnings': issues
            }

    def suggest_solution(self, incident):
        if not incident.description or len(incident.description) < 20:
            return {
                'success': False,
                'error': _('Necesitas una descripción más detallada para sugerir soluciones.'),
                'remaining': self._get_remaining_requests()
            }

        context_parts = [f"Problema: {incident.name}"]
        context_parts.append(f"Descripción: {incident.description[:800]}")
        
        if incident.equipment_id:
            context_parts.append(f"Equipo: {incident.equipment_id.name} ({incident.equipment_id.category or 'general'})")
        
        if incident.type_ids:
            context_parts.append(f"Categorías: {', '.join(t.name for t in incident.type_ids)}")

        prompt = f"""Como técnico IT experto, sugiere 2-3 pasos para resolver:

{chr(10).join(context_parts)}

Responde de forma concisa y práctica. Máximo 150 palabras."""

        result = self._call_openrouter(prompt, max_tokens=250)
        
        if result['success']:
            return {
                'success': True,
                'suggestion': result['content'],
                'remaining': result['remaining']
            }
        return result
