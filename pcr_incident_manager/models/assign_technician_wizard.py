from odoo import models, fields, api

class AssignTechnicianWizard(models.TransientModel):
    """
    Wizard para asignar técnico a múltiples incidencias.
    Se invoca desde la vista lista con registros seleccionados.
    """
    _name = 'pcr_incident_manager.assign.technician.wizard'
    _description = 'Asigna técnico a incidencias'

    technician_id = fields.Many2one(
        'pcr_incident_manager.technician',
        string='Técnico',
        required=True
    )
    
    incident_ids = fields.Many2many(
        'pcr_incident_manager.incident',
        'pcr_assign_wiz_incident_rel',
        'wizard_id',
        'incident_id',
        string='Incidencias elegidas',
        readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self._context.get('active_ids', [])
        if active_ids:
            res['incident_ids'] = [(6, 0, active_ids)]
        return res

    def action_assign(self):
        self.incident_ids.write({'technician_id': self.technician_id.id})
        return {'type': 'ir.actions.act_window_close'}
