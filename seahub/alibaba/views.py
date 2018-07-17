# Copyright (c) 2012-2018 Seafile Ltd.
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.shortcuts import render

from seahub.auth.decorators import login_required
try:
    from seahub.settings import WINDOWS_CLIENT_PUBLIC_DOWNLOAD_URL, \
            WINDOWS_CLIENT_VERSION, APPLE_CLIENT_PUBLIC_DOWNLOAD_URL, \
            APPLE_CLIENT_VERSION, WINDOWS_CLIENT_PUBLIC_DOWNLOAD_URL_EN, \
            WINDOWS_CLIENT_VERSION_EN, APPLE_CLIENT_PUBLIC_DOWNLOAD_URL_EN, \
            APPLE_CLIENT_VERSION_EN

except ImportError:
    WINDOWS_CLIENT_PUBLIC_DOWNLOAD_URL = ''
    WINDOWS_CLIENT_VERSION = ''
    APPLE_CLIENT_PUBLIC_DOWNLOAD_URL = ''
    APPLE_CLIENT_VERSION = ''
    WINDOWS_CLIENT_PUBLIC_DOWNLOAD_URL_EN = ''
    WINDOWS_CLIENT_VERSION_EN = ''
    APPLE_CLIENT_PUBLIC_DOWNLOAD_URL_EN = ''
    APPLE_CLIENT_VERSION_EN = ''

@login_required
def alibaba_client_download_view(request):

    return render(request, 'download.html', {
            'windows_client_public_download_url': WINDOWS_CLIENT_PUBLIC_DOWNLOAD_URL,
            'windows_client_version': WINDOWS_CLIENT_VERSION,
            'apple_client_public_download_url': APPLE_CLIENT_PUBLIC_DOWNLOAD_URL,
            'apple_client_version': APPLE_CLIENT_VERSION,
            'windows_client_public_download_url_en': WINDOWS_CLIENT_PUBLIC_DOWNLOAD_URL_EN,
            'windows_client_version_en': WINDOWS_CLIENT_VERSION_EN,
            'apple_client_public_download_url_en': APPLE_CLIENT_PUBLIC_DOWNLOAD_URL_EN,
            'apple_client_version_en': APPLE_CLIENT_VERSION_EN,
        })
