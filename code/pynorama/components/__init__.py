from pynorama import notification
ADDON_PREFIX = "add_"

logger = notification.Logger("app")

__all__ = [
    "background",
    "mice",
    "layouts",
    "openers"
]

def import_addons():
    from pkgutil import iter_modules
    from importlib import import_module
    import os.path
    directory = os.path.dirname(__file__)
    modules = iter_modules([directory])
    for a_finder, a_name, is_a_package in modules:
        if not a_name.startswith(ADDON_PREFIX):
            continue
        addon_name = a_name[len(ADDON_PREFIX):]
        logger.debug('Adding "{addon}" on app...'.format(addon=addon_name))
        try:
            import_module("." + a_name, __name__)
        except:
            logger.log_error(
                'Error adding "{addon}" on app'.format(addon=addon_name)
            )
            logger.log_exception()

