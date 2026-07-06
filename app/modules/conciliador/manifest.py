manifest = {
    "name": "Conciliador de Caixa",
    "slug": "conciliador",
    "version": "1.0.0",
    "description": "Conciliador de caixa para posto e restaurante com importacao de relatorios",
    "is_default": True,
    "dependencies": [],
    "menus": [
        {
            "label": "Conciliador",
            "icon": "calculator",
            "route": "/conciliador",
            "order": 1,
        }
    ],
    "permissions": ["read", "write", "delete"],
    "events_subscriptions": [],
}
