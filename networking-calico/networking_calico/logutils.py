# -*- coding: utf-8 -*-
# Copyright (c) 2015-2016 Tigera, Inc. All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


def logging_exceptions(logger):
    def decorator(fn):
        def wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                logger.exception("Exception in function %s")
                raise

        return wrapped

    return decorator


def recreate_log_handler_locks_using_native_threading():
    """Recreate the locks in log handlers using the native threading lock.

    When eventlet monkey_patched the service, the global and per-handler locks
    created under the logging module will be using the eventlet locks, which
    introduces problems if one wants to use native threading - greenthread
    resources cannot be used across different native threads. Therefore, to
    workaround this, recreate the locks with the native threading ones.

    NOTE: Be careful when using this function. Please ensure it is not
    recreating the locks under the main neutron-server processes. This
    function should be called during runtime on the networking-calico
    processes and is meant to be a quick workaround before openstack/neutron
    fully migrate off of eventlet.

    NOTE: This problem is addressed in the upstream oslo.log library, see
    commit: `94b9dc32ec1f52a582adbd97fe2847f7c87d6c17`. However, it changes
    how the lock is created, and by the time the mech driver is created, the
    locks are already created using the eventlet library. Notice that we
    cannot specify `fix_eventlet=True` due the reasons listed in this neutron
    commit: `0aa154b5ce9dc8da73309fb212843a2b69b68696`.

    NOTE: Unlike the upstream fix in oslo.log library, networking-calico will
    be switched to use native threads ONLY. Thus, there is no need to use the
    `PipeMutex`, which "works across both greenlets and real threads, even at
    the same time".
    """
    try:
        import eventlet
        import logging

        native_threading = eventlet.patcher.original('threading')
        # The logging library uses RLock - see `logging/__init__.py`
        logging._lock = native_threading.RLock()

        for handler_weakref in logging._handlerList:
            # Dereference by calling the weakref.
            handler = handler_weakref()
            # Recreate the locks using the native threading library.
            if handler and hasattr(handler, "lock"):
                # The logging library uses RLock - see
                # `logging/__init__.py:createLock`
                # function in the `Handler` class.
                handler.lock = native_threading.RLock()
    except Exception as e:
        _msg = ("Failed to recreate the locks under logging library "
               "using the native threading library.")
        raise RuntimeError(_msg) from e
