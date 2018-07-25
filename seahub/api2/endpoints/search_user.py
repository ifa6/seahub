# Copyright (c) 2012-2016 Seafile Ltd.
import os
import sys
import logging

from django.db.models import Q
from django.conf import settings as django_settings

from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from seaserv import ccnet_api

from seahub.api2.authentication import TokenAuthentication
from seahub.api2.throttling import UserRateThrottle
from seahub.api2.utils import api_error
from seahub.utils import is_valid_email, is_org_context
from seahub.base.accounts import User
from seahub.base.templatetags.seahub_tags import email2nickname, \
        email2contact_email
from seahub.profile.models import Profile
from seahub.contacts.models import Contact
from seahub.avatar.templatetags.avatar_tags import api_avatar_url
from seahub.avatar.util import get_alibaba_user_avatar_url

from seahub.settings import ENABLE_GLOBAL_ADDRESSBOOK, \
    ENABLE_SEARCH_FROM_LDAP_DIRECTLY

logger = logging.getLogger(__name__)

try:
    from seahub.settings import CLOUD_MODE
except ImportError:
    CLOUD_MODE = False

try:
    current_path = os.path.dirname(os.path.abspath(__file__))
    seafile_conf_dir = os.path.join(current_path, \
            '../../../../../conf')
    sys.path.append(seafile_conf_dir)
    from seahub_custom_functions import custom_search_user
    CUSTOM_SEARCH_USER = True
except ImportError as e:
    CUSTOM_SEARCH_USER = False

from seahub.alibaba.models import AlibabaProfile


class SearchUser(APIView):
    """ Search user from alibaba profile
    """
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    def get(self, request, format=None):

        q = request.GET.get('q', None)
        if not q:
            error_msg = 'q invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        sorted_users = []
        username = request.user.username
        current_user_profile = AlibabaProfile.objects.get_profile(username)
        if not current_user_profile:
            # users.query
            users = AlibabaProfile.objects.filter(work_status='A').filter(
                    Q(emp_name__icontains=q) | Q(pinyin_name=q) | Q(work_no=q) | \
                    Q(nick_name__icontains=q) | Q(pinyin_nick=q)).order_by('dept_name')

            sorted_users = sorted(users,
                    key=lambda user: len(user.dept_name.split('-')), reverse=True)
        else:
            users = AlibabaProfile.objects.filter(work_status='A').filter(
                    Q(emp_name__icontains=q) | Q(pinyin_name=q) | Q(work_no=q) | \
                    Q(nick_name__icontains=q) | Q(pinyin_nick=q))

            # current user's dept is "A-B-C-D"
            current_user_dept_name = current_user_profile.dept_name

            # [u'A', u'A-B', u'A-B-C', u'A-B-C-D']
            current_user_dept_name_structure = []
            for idx, val in enumerate(current_user_dept_name.split('-')):
                if idx == 0:
                    current_user_dept_name_structure.append(val)
                else:
                    current_user_dept_name_structure.append(
                            current_user_dept_name_structure[-1] + '-' + val)

            for item in reversed(current_user_dept_name_structure):

                dept_match_list = []
                for user in users:
                    if user in sorted_users:
                        continue

                    user_dept_name = user.dept_name
                    if user_dept_name.startswith(item):
                        dept_match_list.append(user)

                dept_match_list = sorted(dept_match_list,
                        key=lambda user: len(user.dept_name.split('-')))

                sorted_users.extend(dept_match_list)

            dept_unmatch_list = []
            for user in users:
                if user not in sorted_users:
                    dept_unmatch_list.append(user)

            dept_unmatch_list = sorted(dept_unmatch_list,
                    key=lambda user: len(user.dept_name.split('-')))
            sorted_users.extend(dept_unmatch_list)

        result = []
        for user in sorted_users:

            if user.uid == username:
                continue

            user_info = {}
            user_info['uid'] = user.uid
            user_info['personal_photo_url'] = get_alibaba_user_avatar_url(user.uid)
            user_info['emp_name'] = user.emp_name or ''
            user_info['nick_name'] = user.nick_name or ''
            user_info['work_no'] = user.work_no or ''

            if request.LANGUAGE_CODE == 'zh-cn':
                user_info['post_name'] = user.post_name or ''
                user_info['dept_name'] = user.dept_name or ''
            else:
                user_info['post_name'] = user.post_name_en or ''
                user_info['dept_name'] = user.dept_name_en or ''

            result.append(user_info)

        return Response({"users": result})


def format_searched_user_result(request, users, size):
    results = []

    for email in users:
        url, is_default, date_uploaded = api_avatar_url(email, size)
        results.append({
            "email": email,
            "avatar_url": request.build_absolute_uri(url),
            "name": email2nickname(email),
            "contact_email": email2contact_email(email),
        })

    return results

def search_user_from_ccnet(q):
    users = []

    db_users = ccnet_api.search_emailusers('DB', q, 0, 10)
    users.extend(db_users)

    count = len(users)
    if count < 10:
        ldap_imported_users = ccnet_api.search_emailusers('LDAP', q, 0, 10 - count)
        users.extend(ldap_imported_users)

    count = len(users)
    if count < 10 and ENABLE_SEARCH_FROM_LDAP_DIRECTLY:
        all_ldap_users = ccnet_api.search_ldapusers(q, 0, 10 - count)
        users.extend(all_ldap_users)

    # `users` is already search result, no need search more
    email_list = []
    for user in users:
        email_list.append(user.email)

    return email_list

def search_user_from_profile(q):
    # 'nickname__icontains' for search by nickname
    # 'contact_email__icontains' for search by contact email
    users = Profile.objects.filter(Q(nickname__icontains=q) | \
            Q(contact_email__icontains=q)).values('user')

    email_list = []
    for user in users:
        email_list.append(user['user'])

    return email_list

def search_user_from_profile_with_limits(q, limited_emails):
    # search within limited_emails
    users = Profile.objects.filter(Q(user__in=limited_emails) &
            (Q(nickname__icontains=q) | Q(contact_email__icontains=q))).values('user')

    email_list = []
    for user in users:
        email_list.append(user['user'])

    return email_list

def search_user_when_global_address_book_disabled(request, q):

    email_list = []
    username = request.user.username

    # search from contact
    # get user's contact list
    contacts = Contact.objects.get_contacts_by_user(username)
    for contact in contacts:
        # search user from contact list
        if q in contact.contact_email:
            email_list.append(contact.contact_email)

    # search from profile, limit search range in user's contacts
    limited_emails = []
    for contact in contacts:
        limited_emails.append(contact.contact_email)

    email_list += search_user_from_profile_with_limits(q, limited_emails)

    current_user = User.objects.get(email=username)
    if is_valid_email(q) and current_user.role.lower() != 'guest':
        # if `q` is a valid email and current is not a guest user
        email_list.append(q)

        # get user whose `contact_email` is `q`
        users = Profile.objects.filter(contact_email=q).values('user')
        for user in users:
            email_list.append(user['user'])

    return email_list
