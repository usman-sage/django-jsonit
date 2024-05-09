"""
A JSON response always returns a JSON-encoded dictionary. The dictionary
will always contain the following three keys:

``success``

    True or False

``details``

    A dictionary containing any success / failure details.

``messages``

    A list of message dictionaries. Each message dictionary contains a
    ``class`` (a string of HTML classes) and a ``message`` key. This list will
    always be empty for successful responses where a if a suggested redirection
    URL is provided.

If the response is successful then an additional key, ``redirect`` will also
be provided which may be ``null`` or contain a suggested next URL.

An example success:

.. code-block:: js

    {
        'success': true,
        'details': {},
        'messages': [
            {'class': '', 'message': 'some message'},
        ],
        'redirect': null
    }

If an exception is passed (via the ``exception`` parameter), ``details`` and
``messages`` will be emptied, ``success`` will be set to ``False``, and an
``exception`` key will be added to the response.

An example exception:

.. code-block:: js

    {
        'success': false,
        'details': {},
        'messages': [],
        'exception': 'error message'
    }

If the project's ``DEBUG`` setting is ``False``, exception will just be set to
``True``.
"""
from django import http
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from jsonit.encoder import encode


class JSONResponse(http.HttpResponse):
    """
    Return a JSON encoded HTTP response.
    """

    def __init__(self, request, details=None, success=True, exception=None,
                 redirect=None, extra_context=None):
        """
        :param request: The current ``HTTPRequest``. Required so that any
            ``django.contrib.messages`` can be retrieved.
        :param details: An optional dictionary of extra details to be encoded
            as part of the response.
        :param success: Whether the request was considered successful. Defaults
            to ``True``.
        :param exception: Used to build an exception JSON response. Not
            usually needed unless the need to handle exceptions manually
            arises. See the :class:`~.JSONExceptionMiddleware` to handle AJAX
            exceptions automatically.
        :param redirect: The URL to which the JavaScript should redirect.
        :returns: An HTTPResponse containing a JSON encoded dictionary with a
            content type of ``application/json``.
        """
        self.request = request
        self.success = success
        self.details = details or {}
        self.extra_context = extra_context or {}
        if redirect is not None:
            redirect = request.build_absolute_uri(redirect)
        self.redirect = redirect
        assert isinstance(self.details, dict)
        content = self.build_json(exception)
        super(JSONResponse, self).__init__(content=content,
                                           content_type='application/json')

    def build_json(self, exception=None):
        """Build the JSON dictionary."""
        content = {
            'success': self.success,
            'details': self.details,
            'messages': [],
        }
        if exception is not None:
            content['success'] = False
            content['details'] = {}
            if hasattr(exception, 'message'):
                exception = exception.message
            else:
                exception = '%s: %s' % (_('Internal error'), exception)
            content['exception'] = exception
        else:
            content['messages'] = self.get_messages()
            redirect = self.get_redirect()
            if redirect:
                content['redirect'] = self.redirect
        if self.extra_context:
            content['extra_context'] = self.extra_context
        try:
            return encode(content)
        except Exception as e:
            if exception is not None:
                raise
            return self.build_json(e)

    def get_messages(self):
        """
        Consume and return a list of the user's messages, unless this is a
        redirection (in which case, return an empty list).
        """
        if self.success and self.redirect:
            return []
        return list(messages.get_messages(self.request))

    def get_redirect(self):
        """
        Return the redirection URL, as long as this is a successful
        response (i.e. :attr:`success` is ``True``).
        """
        if not self.success:
            return None
        return self.redirect


class JSONFormResponse(JSONResponse):
    """
    Return a JSON response, handling form errors.

    Accepts a ``forms`` keyword argument which should be a list of forms to
    be validated.

    If any of the forms contain errors, a ``form_errors`` key
    will be added to the ``details`` dictionary, containing the HTML ids of
    fields and a list of messages for each.

    The ``__all__`` key is used for any form-wide error messages.

    An example failure::

        {
            'success': False,
            'details': {
                'form_errors': {
                    '__all__': ['some error'],
                    'some_field_id': ['some error'],
                }
            },
            'messages': [
                {'class': 'error', 'message': 'some message'},
                {'class': '', 'message': 'some message'},
            ]
        }
    """

    def __init__(self, *args, **kwargs):
        """
        In addition to the standard :class:`JSONResponse` arguments, one
        additional keyword argument is available.

        :param forms: A list of forms to validate against.
        """
        self.forms = kwargs.pop('forms')
        super(JSONFormResponse, self).__init__(*args, **kwargs)

    def build_json(self, *args, **kwargs):
        """
        Check for form errors before building the JSON dictionary.
        """
        self.get_form_errors()
        return super(JSONFormResponse, self).build_json(*args, **kwargs)

    def get_form_errors(self):
        """
        Validate the forms, adding the ``form_errors`` key to :attr:`details`
        containing any form errors.

        If any of the forms do not validate, :attr:`success` will be set to
        ``False``.
        """
        forms = self.forms or ()
        for form in forms:
            for field, errors in form.errors.items():
                self.success = False
                if field != '__all__':
                    field = form[field].auto_id
                if field:
                    form_errors = self.details.setdefault('form_errors', {})
                    error_list = form_errors.setdefault(field, [])
                    error_list.extend(errors)

def is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'

