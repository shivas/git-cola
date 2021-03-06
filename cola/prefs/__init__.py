from cola.prefs.view import PreferencesView
from cola.prefs.view import diff_font
from cola.prefs.view import tab_width
from cola.prefs.model import PreferencesModel
from cola.prefs.controller import PreferencesController


def preferences(model=None):
    if model is None:
        model = PreferencesModel()
    prefs = PreferencesView(model)
    ctl = PreferencesController(model, prefs)
    prefs.show()
    prefs.raise_()
    return ctl
