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
from seahub.group.utils import is_group_member

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

            try:
                AlibabaMessageQueue.objects.add_lock(message.id)

                message_dict = json.loads(message.message_body)
                leave_work_no = message_dict['leaveWorkNo']
                super_work_no = message_dict['superWorkNo']

                leave_work_profile = AlibabaProfile.objects.get_profile_by_work_no(leave_work_no, False)
                if not leave_work_profile:
                    logger.debug('leaveWorkNo %s not found in alibaba profile.' % leave_work_no)
                    continue

                super_work_profile = AlibabaProfile.objects.get_profile_by_work_no(super_work_no)
                if not super_work_profile:
                    logger.debug('superWorkNo%s not found in alibaba profile.' % super_work_no)
                    continue

                leave_ccnet_email = leave_work_profile.uid
                super_ccnet_email = super_work_profile.uid

                ccnet_user_obj = ccnet_api.get_emailuser(leave_ccnet_email)
                if ccnet_user_obj:
                    ccnet_api.update_emailuser('DB', ccnet_user_obj.id, '!', 0, 0)

                leave_owned_repos = seafile_api.get_owned_repo_list(
                        leave_ccnet_email, ret_corrupted=False)

                for repo in leave_owned_repos:

                    if seafile_api.repo_has_been_shared(repo.id, including_groups=True):

                        # get repo shared to user/group/public list
                        shared_users = seafile_api.list_repo_shared_to(
                                leave_ccnet_email, repo.id)
                        shared_groups = seafile_api.list_repo_shared_group_by_user(
                                leave_ccnet_email, repo.id)
                        pub_repos = seafile_api.list_inner_pub_repos_by_owner(leave_ccnet_email)

                        # transfer repo
                        seafile_api.set_repo_owner(repo.id, super_ccnet_email)

                        # reshare repo to user
                        for shared_user in shared_users:

                            shared_username = shared_user.user
                            if super_ccnet_email== shared_username:
                                continue

                            seafile_api.share_repo(repo.id, super_ccnet_email,
                                    shared_username, shared_user.perm)

                        # reshare repo to group
                        for shared_group in shared_groups:

                            shared_group_id = shared_group.group_id
                            if not is_group_member(shared_group_id, super_ccnet_email):
                                continue

                            seafile_api.set_group_repo(repo.id, shared_group_id,
                                    super_ccnet_email, shared_group.perm)

                        # check if current repo is pub-repo
                        # if YES, reshare current repo to public
                        for pub_repo in pub_repos:

                            if repo.id != pub_repo.id:
                                continue

                            seafile_api.add_inner_pub_repo(repo.id, pub_repo.permission)
                            break
                    else:
                        seafile_api.remove_repo(repo.id)
            except Exception as e:
                logger.error(e)

        for message in messages:
            AlibabaMessageQueue.objects.remove_lock(message.id)
            AlibabaMessageQueue.objects.mark_message_consumed(message.id)

        self.stdout.write('Done.\n')
