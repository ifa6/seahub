import os
import logging
import urllib2
from django.core.files import File
from django.utils import translation

from seahub.avatar.models import Avatar
from seahub.avatar.signals import avatar_updated
from seahub.alibaba.models import AlibabaProfile


logger = logging.getLogger(__name__)

def get_ali_user_profile_dict(request, uid):
    if translation.get_language() != 'zh-cn':
        use_en = True
    else:
        use_en = False

    ali_p = AlibabaProfile.objects.get_profile(uid)
    if ali_p:
        work_no = ali_p.work_no
        post_name = ali_p.post_name_en if use_en else ali_p.post_name
        dept = ali_p.dept_name_en if use_en else ali_p.dept_name
    else:
        work_no = ''
        post_name = ''
        dept = ''

    return {
        "work_no": work_no,
        "post_name": post_name,
        "dept_name": dept,
    }
