# Copyright (c) 2012-2016 Seafile Ltd.
# encoding: utf-8

import json
import time
import logging
from random import randint

from django.core.management.base import BaseCommand

from seaserv import seafile_api, ccnet_api

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

        messages = AlibabaMessageQueue.objects.filter(lock_version=0).filter(is_consumed=0). \
                filter(topic=ALIBABA_MESSAGE_TOPIC_LEAVE_FILE_HANDOVER)

        for message in messages:
            try:
                message_dict = json.loads(message.message_body)
                leave_work_no = message_dict['leaveWorkNo']
                super_work_no = message_dict['superWorkNo']

                # existence check for leave worker
                # `False` parameter for select all workers in alibaba profile
                leave_work_profile = AlibabaProfile.objects.get_profile_by_work_no(leave_work_no, False)
                if not leave_work_profile:
                    logger.error('leaveWorkNo %s not found in alibaba profile.' % leave_work_no)
                    continue

                leave_ccnet_email = leave_work_profile.uid
                if not leave_ccnet_email:
                    logger.error('uid not found for leaveWorkNo %s.' % leave_work_no)
                    continue

                # existence check for super worker
                # No `False` parameter, only select workers at work
                super_work_profile = AlibabaProfile.objects.get_profile_by_work_no(super_work_no)
                if not super_work_profile:
                    logger.error('superWorkNo %s not found in alibaba profile.' % super_work_no)
                    continue

                super_ccnet_email = super_work_profile.uid
                if not super_ccnet_email:
                    logger.error('uid not found for superWorkNo %s.' % super_work_no)
                    continue

                # lock message
                AlibabaMessageQueue.objects.add_lock(message.id)

                # inactive user
                ccnet_user_obj = ccnet_api.get_emailuser(leave_ccnet_email)
                if ccnet_user_obj:
                    ccnet_api.update_emailuser('DB', ccnet_user_obj.id, '!', 0, 0)

                # delete or transfer repos of leave worker
                leave_owned_repos = seafile_api.get_owned_repo_list(leave_ccnet_email)

                for repo in leave_owned_repos:

                    should_delete = True
                    if seafile_api.is_inner_pub_repo(repo.id):
                        seafile_api.set_repo_owner(repo.id, super_ccnet_email)
                        should_delete = False

                    if seafile_api.repo_has_been_shared(repo.id, including_groups=True):

                        # get repo shared to user/group/public list
                        shared_users = seafile_api.list_repo_shared_to(
                                leave_ccnet_email, repo.id)
                        shared_groups = seafile_api.list_repo_shared_group_by_user(
                                leave_ccnet_email, repo.id)

                        # transfer repo
                        seafile_api.set_repo_owner(repo.id, super_ccnet_email)

                        # reshare repo to user
                        for shared_user in shared_users:

                            shared_username = shared_user.user
                            if super_ccnet_email == shared_username:
                                continue

                            seafile_api.share_repo(repo.id, super_ccnet_email,
                                    shared_username, shared_user.perm)

                        # reshare repo to group
                        for shared_group in shared_groups:

                            shared_group_id = shared_group.group_id
                            seafile_api.set_group_repo(repo.id, shared_group_id,
                                    super_ccnet_email, shared_group.perm)

                        should_delete = False

                    if should_delete:
                        seafile_api.remove_repo(repo.id)

                AlibabaMessageQueue.objects.remove_lock(message.id)
                AlibabaMessageQueue.objects.mark_message_consumed(message.id)
            except Exception as e:
                logger.error(e)

        self.stdout.write('Done.\n')
