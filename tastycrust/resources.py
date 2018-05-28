#!/usr/bin/env python
# -*- coding: utf-8


import inspect
from functools import wraps

import collections
from django.conf.urls import url
from tastypie.utils import trailing_slash

__all__ = ['ActionResourceMixin', 'action', 'is_action']


def is_action(obj):
    return inspect.isfunction(obj) and getattr(obj, 'is_action', False)


def action(meta=None, name=None, url=None, static=False, fields={}, summary=None, type_list=True,
           allowed=None, login_required=False, throttled=False, hidden_from_doc=False):
    if isinstance(name, collections.Callable):  # Used as @action without invoking
        wrapped = name
        name = None
    else:  # Used as @action(...)
        wrapped = None

    def decorator(func):
        if not hidden_from_doc and meta:
            if not hasattr(meta, 'extra_actions'):
                meta.extra_actions = []
            for method in allowed:
                extra_action = {
                    "name": name,
                    "http_method": method,
                    "resource_type": 'list' if type_list else None,
                    "summary": summary,
                    "fields": fields,
                    "authRequired": login_required,
                    "notes": func.__doc__
                }
                meta.extra_actions.append(extra_action)

        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if allowed is not None:
                self.method_check(request, allowed)
            if login_required:
                self.is_authenticated(request)
            if throttled:
                self.throttle_check(request)
                self.log_throttled_access(request)
            return func(self, request, *args, **kwargs)

        wrapper.is_action = True
        wrapper.action_is_static = static
        wrapper.action_name = name
        wrapper.action_url = url

        return wrapper

    if wrapped is not None:
        return decorator(wrapped)
    return decorator


class ActionResourceMixin(object):
    def prepend_urls(self):
        urls = super().prepend_urls()
        action_methods = inspect.getmembers(type(self), predicate=is_action)
        for name, method in action_methods:
            action_name = method.action_name or name
            url_name = 'api_action_' + action_name
            action_url = method.action_url
            if action_url is not None:
                pattern = r'^{action_url}{slash}$'
                action_url = action_url.strip('/')
            elif method.action_is_static:
                pattern = r'^(?P<resource_name>{resource})/{name}{slash}$'
                url_name = 'api_action_static_' + action_name
            else:
                pattern = (r'^(?P<resource_name>{resource})/'
                           r'(?P<{detail_uri}>.*?)/{name}{slash}$')
            pattern = pattern.format(
                action_url=action_url,
                resource=self._meta.resource_name,
                detail_uri=self._meta.detail_uri_name,
                name=action_name, slash=trailing_slash()
            )
            urls.insert(0, url(pattern, self.wrap_view(name), name=url_name))
        return urls
