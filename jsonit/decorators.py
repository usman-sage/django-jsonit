from functools import wraps

from jsonit.http import JSONResponse, is_ajax


def catch_ajax_exceptions(func):
    """
    Catches exceptions which occur when using an AJAX request.

    These exceptions will be returned using a :class:`JSONResponse` rather than
    letting the exception propogate.
    """

    @wraps(func)
    def dec(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except Exception as e:
            if is_ajax(request):
                return JSONResponse(request, exception=e)
            raise

    return dec
