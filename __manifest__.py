# -*- coding: utf-8 -*-
{
    'name': "Gestión de incidencias IT",
    'summary': "Gestión inteligente de incidencias IT y mantenimiento con priorización asistida por IA",
    'description': """
PCR Incident Manager - Gestión de Incidencias IT

Módulo de gestión de incidencias IT y mantenimiento de equipos.

Características principales:
* Gestión completa de incidencias (CRUD, estados, prioridades)
* Catálogo de equipos con seguimiento de incidencias
* Gestión de técnicos y asignación automática
* Asistencia IA para sugerir prioridades y soluciones (OpenRouter)
* Notificaciones por correo electrónico
* Códigos QR para acceso rápido a incidencias
* Informes PDF de incidencias
* Vistas Kanban, calendario, gráficos y tabla dinámica
* Seguridad por roles (Técnico / Administrador)
* Soporte multiidioma (ES/EN)

Requisitos:
* Odoo 17.0
* Módulos: base, mail, contacts
* (Opcional) Librería Python 'qrcode' para generar códigos QR
* (Opcional) Clave API de OpenRouter para funciones de IA
    """,
    'author': "ImPavloh",
    'maintainer': "ImPavloh",
    'website': "https://github.com/ImPavloh/pcr_incident_manager",
    'support': "https://github.com/ImPavloh/pcr_incident_manager/issues",
    'license': 'LGPL-3',
    'category': 'Helpdesk',
    'version': '17.0.1.0.0',
    'depends': ['base', 'mail', 'contacts', 'product'],
    'data': [
        'data/sequences.xml',
        'data/mail_templates.xml',
        'report/incident_report.xml',
        'security/groups.xml',
        'security/rules.xml',
        'security/ir.model.access.csv',
        'views/ai_service.xml',
        'views/incident.xml',
        'views/equipment.xml',
        'views/equipment_category.xml',
        'views/technician.xml',
        'views/incident_type.xml',
        'views/menus.xml',
        'views/settings.xml',
        'views/assign_technician_wizard.xml',
        'views/suggest_priority_wizard.xml',
        'views/suggest_solution_wizard.xml',
        'views/res_partner.xml',
    ],
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/banner_screenshot.png', 'static/description/screenshot-01.png', 'static/description/screenshot-02.png', 'static/description/screenshot-03.png', 'static/description/screenshot-04.png'],
}
