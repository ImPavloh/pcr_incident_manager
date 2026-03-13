# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import base64
import io

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False


class PcrIncident(models.Model):
    """
    Modelo principal
    Gestiona el ciclo de vida completo: creación, asignación,
    resolución y cierre. Con integración con mail.thread
    para seguimiento y notificaciones si es posible.
    """
    _name = 'pcr_incident_manager.incident'
    _description = 'Incidencia'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_created desc'

    # Campos básicos
    name = fields.Char(
        string='Título',
        required=True,
        tracking=True
    )
    
    reference = fields.Char(
        string='Referencia',
        readonly=True,
        copy=False,
        default='Nuevo'
    )
    
    description = fields.Text(
        string='Descripción',
        tracking=True
    )

    date_created = fields.Datetime(
        string='Fecha de creación', 
        default=fields.Datetime.now, 
        readonly=True,
        tracking=True
    )

    date_closed = fields.Datetime(
        string='Fecha de cierre',
        tracking=True
    )
    
    solution = fields.Text(
        string='Solución',
        help='Descripción de cómo se resolvió la incidencia',
        tracking=True
    )
    
    state = fields.Selection([
        ('open', 'Abierta'),
        ('in_progress', 'En proceso'),
        ('resolved', 'Resuelta'),
        ('closed', 'Cerrada'),
        ('cancelled', 'Cancelada'),
    ],
        string='Estado',
        default='open',
        required=True,
        tracking=True
    )
    
    priority = fields.Selection([
        ('0', 'Baja'),
        ('1', 'Normal'),
        ('2', 'Alta'),
        ('3', 'Urgente'),
    ],
        string='Prioridad',
        default='1',
        required=True,
        tracking=True
    )
    
    # relaciones many2one
    equipment_id = fields.Many2one(
        'pcr_incident_manager.equipment', 
        string='Equipo', 
        ondelete='restrict',
        tracking=True
    )

    technician_id = fields.Many2one(
        'pcr_incident_manager.technician', 
        string='Técnico asignado', 
        ondelete='set null',
        tracking=True
    )
    
    # relacion many2many
    type_ids = fields.Many2many(
        'pcr_incident_manager.incident.type', 
        'pcr_im_incident_type_rel',
        'incident_id',
        'type_id',
        string='Tipos de incidencia',
        tracking=True
    )

    # Campo computado con función inversa
    days_open = fields.Integer(
        string='Días abierta',
        compute='_compute_days_open',
        inverse='_inverse_days_open',
        store=True,
        search='_search_days_open',
    )

    qr_url = fields.Char(
        string='URL QR',
        compute='_compute_qr_url',
        help='URL para el código QR de acceso directo'
    )

    qr_code = fields.Binary(
        string='Código QR',
        compute='_compute_qr_code',
        help='Código QR para acceder directamente a esta incidencia'
    )

    # Validaciones para campos únicos
    _sql_constraints = [
        ('reference_unique', 'UNIQUE(reference)', 'La referencia de la incidencia tiene que ser única'),
        ('name_not_empty', "CHECK(name IS NOT NULL AND name != '')", 'El título de la incidencia no puede estar vacío'),
    ]

    def _search_days_open(self, operator, value):
        """Deja buscar incidencias por días abierta"""

        today = fields.Datetime.now()
        if operator == '>':
            date_limit = today - timedelta(days=value)
            return [('date_created', '<', date_limit), ('state', 'in', ['open', 'in_progress'])]
        elif operator == '<':
            date_limit = today - timedelta(days=value)
            return [('date_created', '>', date_limit)]
        return []

    @api.depends('date_created', 'date_closed', 'state')
    def _compute_days_open(self):
        """Calcula días transcurridos desde creación hasta cierre (o hasta hoy)"""

        for record in self:
            if record.state in ['closed', 'resolved'] and record.date_closed:
                delta = record.date_closed - record.date_created
                record.days_open = max(0, delta.days)
            elif record.date_created:
                delta = fields.Datetime.now() - record.date_created
                record.days_open = max(0, delta.days)
                
            else:
                record.days_open = 0

    def _inverse_days_open(self):
        """
        Función inversa que deja modificar la fecha de creación
        ajustándola según los días abierta especificados
        Si la incidencia está cerrada se ajusta la fecha de cierre
        """
        for record in self:
            if record.days_open < 0:
                continue
            
            if record.state in ['closed', 'resolved'] and record.date_created:
                record.date_closed = record.date_created + timedelta(days=record.days_open)

            elif record.date_created:
                record.date_created = fields.Datetime.now() - timedelta(days=record.days_open)

    def _get_incident_url(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web#id={self.id}&model={self._name}&view_type=form"

    def _compute_qr_url(self):
        show_pdf = self.env['ir.config_parameter'].sudo().get_param('pcr_incident_manager.show_qr_in_pdf', 'True')
        show_pdf = str(show_pdf).lower() in ('1', 'true', 'yes')
        for record in self:
            if record.id and show_pdf:
                record.qr_url = record._get_incident_url()
            else:
                record.qr_url = False

    def _compute_qr_code(self):
        """Genera código QR con URL de acceso directo a la incidencia"""

        show_views = self.env['ir.config_parameter'].sudo().get_param('pcr_incident_manager.show_qr_in_views', 'True')
        show_views = str(show_views).lower() in ('1', 'true', 'yes')
        for record in self:
            if not QRCODE_AVAILABLE or not record.id or not show_views:
                record.qr_code = False
                continue

            try:
                url = record._get_incident_url()

                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=6,
                    border=2,
                )
                qr.add_data(url)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")

                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                record.qr_code = base64.b64encode(buffer.getvalue()).decode('utf-8')
            except Exception:
                record.qr_code = False

    @api.onchange('state')
    def _onchange_state(self):
        if self.state in ['resolved', 'closed'] and not self.date_closed:
            self.date_closed = fields.Datetime.now()
        elif self.state in ['open', 'in_progress']:
            self.date_closed = False

    @api.constrains('state', 'technician_id')
    def _check_technician_on_close(self):
        for record in self:
            if record.state in ['resolved', 'closed'] and not record.technician_id:
                raise ValidationError(
                    _('No se puede resolver o cerrar una incidencia sin técnico asignado')
                )

    @api.constrains('state', 'solution')
    def _check_solution_on_resolve(self):
        for record in self:
            if record.state in ['resolved', 'closed'] and not record.solution:
                raise ValidationError(
                    _('No se puede resolver o cerrar una incidencia sin describir la solución')
                )

    @api.constrains('description')
    def _check_description_length(self):
        for record in self:
            if record.description and len(record.description.strip()) < 10:
                raise ValidationError(
                    _('La descripción debe tener al menos 10 caracteres para una mejor trazabilidad')
                )

    @api.constrains('priority')
    def _check_priority_present(self):
        for record in self:
            if not record.priority:
                raise ValidationError(
                    _('La prioridad es obligatoria. Elige una prioridad antes de guardar')
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nuevo') == 'Nuevo':
                vals['reference'] = self.env['ir.sequence'].next_by_code('pcr_incident_manager.incident') or 'Nuevo'
        records = super().create(vals_list)

        # si se ha asignado un técnico se envia la notificación
        for record in records:
            if record.technician_id:
                record._send_technician_notification()

        return records

    def unlink(self):
        """
        Sobreescribe unlink para validar antes de eliminar
        No deja eliminar incidencias en progreso o resueltas
        """
        for record in self:
            if record.state == 'in_progress':
                raise ValidationError(
                    _('No se puede eliminar la incidencia %s porque está en progreso. '
                      'Primero ciérrala o cancélala.') % record.reference
                )
            
            if record.state == 'resolved':
                raise ValidationError(
                    _('No se puede eliminar la incidencia %s porque está resuelta. '
                      'Las incidencias resueltas deben archivarse, no eliminarse.') % record.reference
                )
            
        return super().unlink()

    def write(self, vals):
        old_technicians = {rec.id: rec.technician_id for rec in self}
        result = super().write(vals)
        
        # si se ha cambiado el técnico se envia la notificación
        if 'technician_id' in vals:
            for record in self:
                new_technician = record.technician_id
                old_technician = old_technicians.get(record.id)

                if new_technician and new_technician != old_technician:
                    record._send_technician_notification()

        return result

    def _check_mail_server_configured(self):
        mail_server = self.env['ir.mail_server'].sudo().search([], limit=1)
        return bool(mail_server)

    def _post_notification_message(self, message):
        self.ensure_one()
        subtype = self.env.ref('mail.mt_note')
        self.message_post(
            body=f"{message}",
            message_type='notification',
            subtype_id=subtype.id,
        )

    def _send_technician_notification(self):
        """Envía correo al técnico asignado. Registra resultado en el chatter."""

        self.ensure_one()
        
        # Verificar si hay servidor de correo configurado
        if not self._check_mail_server_configured():
            self._post_notification_message(
                _('Notificación NO enviada: No hay servidor de correo configurado.\n'
                  'Para activar notificaciones por correo ve a: Ajustes - Técnico - Servidores de correo de salida')
            )
            return False
        
        if not self.technician_id:
            return False
        
        # comprobar que el técnico tenga correo
        email = self.technician_id.email or (self.technician_id.user_id.email if self.technician_id.user_id else False)
        
        if not email:
            self._post_notification_message(
                _('Notificación NO enviada: El técnico %s no tiene correo configurado.\nAñade un correo al técnico para recibir notificaciones.') % self.technician_id.name
            )
            return False
        
        template = self.env.ref('pcr_incident_manager.mail_template_incident_assigned')

        # enviar correo
        try:
            template.send_mail(self.id, force_send=False)
            self._post_notification_message(
                _('Notificación enviada a %s (%s)') % (self.technician_id.name, email)
            )
            return True
        except Exception as e:
            self._post_notification_message(
                _('Error al enviar notificación: %s') % str(e)
            )
            return False


    # Acciones de cambio de estado
    
    def action_start(self):
        """Inicia el trabajo en la incidencia."""
        self.write({'state': 'in_progress'})

    def action_resolve(self):
        for record in self:
            if not record.solution:
                raise ValidationError(
                    _('Debes describir la solución antes de resolver la incidencia')
                )
            
        self.write({
            'state': 'resolved',
            'date_closed': fields.Datetime.now()
        })

    def action_close(self):
        self.write({
            'state': 'closed',
            'date_closed': fields.Datetime.now()
        })

    def action_reopen(self):
        """
        Reabre una incidencia resuelta o cerrada para retrabajar.
        No permite reabrir incidencias canceladas (deben crearse de nuevo)
        """
        for record in self:
            if record.state == 'cancelled':
                raise ValidationError(
                    _('No se puede reabrir una incidencia cancelada. '
                      'Crea una nueva incidencia si es necesario.')
                )
            if record.state not in ['resolved', 'closed']:
                raise ValidationError(
                    _('Solo se pueden reabrir incidencias resueltas o cerradas.')
                )
        self.write({
            'state': 'in_progress',
            'date_closed': False
        })

    def action_cancel(self):
        """Cancela la incidencia. Representa incidencias descartadas sin trabajo realizado."""
        for record in self:
            if record.state != 'open':
                raise ValidationError(
                    _('Solo se pueden cancelar incidencias en estado Abierta. '
                      'La incidencia %s está en estado %s.') % (record.reference, record.state)
                )
            
        self.write({
            'state': 'cancelled',
            'date_closed': fields.Datetime.now()
        })


    # Acciones IA
    
    def action_suggest_priority(self):
        """Abre wizard de sugerencia de prioridad con IA."""

        return {
            'name': 'Sugerir prioridad (IA)',
            'type': 'ir.actions.act_window',
            'res_model': 'pcr_incident_manager.suggest.priority.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id}
        }

    def action_suggest_solution(self):
        """Abre wizard de sugerencia de solución con IA."""
        
        return {
            'name': 'Sugerir solución (IA)',
            'type': 'ir.actions.act_window',
            'res_model': 'pcr_incident_manager.suggest.solution.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id}
        }
