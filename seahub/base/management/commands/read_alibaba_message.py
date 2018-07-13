# Copyright (c) 2012-2016 Seafile Ltd.
# encoding: utf-8

import json
import time
import logging
from random import randint

from django.core.management.base import BaseCommand

from seaserv import seafile_api

from seahub.alibaba.models import AlibabaMessageQueue, AlibabaProfile, \
        ALIBABA_MESSAGE_TOPIC_LEAVE_FILE_HANDOVER

# Get an instance of a logger
logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Read messages from alibaba message queue database table."

    def handle(self, *args, **options):

        random_second = randint(0, 60 * 10)
        time.sleep(random_second)

        self.stdout.write("Start.\n")

        messages = AlibabaMessageQueue.objects.filter(is_consumed=0). \
                filter(topic=ALIBABA_MESSAGE_TOPIC_LEAVE_FILE_HANDOVER)
        for message in messages:

            if message.lock_version == 1:
                continue

            AlibabaMessageQueue.objects.add_lock(message.id)

            message_dict = json.loads(message.message_body)
            leave_work_no = message_dict['leaveWorkNo']
            super_work_no = message_dict['superWorkNo']

            leave_work_profile = AlibabaProfile.objects.get_profile_by_work_no(leave_work_no)
            if not leave_work_profile:
                logger.debug('leaveWorkNo %s not found in alibaba profile.' % leave_work_no)
                continue

            super_work_profile = AlibabaProfile.objects.get_profile_by_work_no(super_work_no)
            if not super_work_profile:
                logger.debug('superWorkNo%s not found in alibaba profile.' % super_work_no)
                continue

            leave_ccnet_email = leave_work_profile.uid
            super_ccnet_email = super_work_profile.uid

            leave_owned_repos = seafile_api.get_owned_repo_list(
                    leave_ccnet_email, ret_corrupted=False)

            for repo in leave_owned_repos:
                if seafile_api.repo_has_been_shared(repo.id, including_groups=True):
                    seafile_api.set_repo_owner(repo.id, super_ccnet_email)
                else:
                    seafile_api.remove_repo(repo.id)

        for message in messages:
            AlibabaMessageQueue.objects.remove_lock(message.id)
            AlibabaMessageQueue.objects.mark_message_consumed(message.id)

        self.stdout.write('Done.\n')
