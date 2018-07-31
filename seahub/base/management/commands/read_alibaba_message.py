# Copyright (c) 2012-2016 Seafile Ltd.
# encoding: utf-8

import json
import time
from random import randint
from constance import config

from django.core.management.base import BaseCommand

from seaserv import seafile_api, ccnet_api
from seahub.utils import clear_token
from seahub.share.utils import share_dir_to_user, share_dir_to_group
from seahub.share.models import ExtraSharePermission
from seahub.profile.models import Profile
from seahub.options.models import UserOptions

from seahub.alibaba.models import AlibabaMessageQueue, AlibabaProfile, \
        ALIBABA_MESSAGE_TOPIC_LEAVE_FILE_HANDOVER

def get_leave_work_ccnet_email(message):

    message_dict = json.loads(message.message_body)
    leave_work_no = message_dict['leaveWorkNo']

    # existence check for leave worker
    # `False` parameter for select all workers in alibaba profile
    leave_work_profile = AlibabaProfile.objects.get_profile_by_work_no(leave_work_no, False)
    if not leave_work_profile:
        print 'leaveWorkNo %s not found in alibaba profile.' % leave_work_no
        return None

    leave_ccnet_email = leave_work_profile.uid
    if not leave_ccnet_email:
        print 'uid not found for leaveWorkNo %s.' % leave_work_no
        return None

    return leave_ccnet_email

def get_super_work_ccnet_email(message):
    message_dict = json.loads(message.message_body)
    super_work_no = message_dict['superWorkNo']

    # existence check for super worker
    # No `False` parameter, only select workers at work
    super_work_profile = AlibabaProfile.objects.get_profile_by_work_no(super_work_no)
    if not super_work_profile:
        print 'superWorkNo %s not found in alibaba profile.' % super_work_no
        return None

    super_ccnet_email = super_work_profile.uid
    if not super_ccnet_email:
        print 'uid not found for superWorkNo %s.' % super_work_no
        return None

    return super_ccnet_email

def actions_for_leave_worker(ccnet_user_obj):

    email = ccnet_user_obj.email

    # inactive user
    ccnet_api.update_emailuser('DB', ccnet_user_obj.id, '!', 0, 0)

    # remove shared in repos
    shared_in_repos = seafile_api.get_share_in_repo_list(email, -1, -1)
    for r in shared_in_repos:
        seafile_api.remove_share(r.repo_id, r.user, email)

    # remove extra(admin) permission
    ExtraSharePermission.objects.filter(share_to=email).delete()

    # clear web api and repo sync token
    clear_token(email)

    # remove current user from joined groups
    ccnet_api.remove_group_user(email)

    # remove seahub profile
    Profile.objects.delete_profile_by_user(email)

    # remove terms and conditions
    if config.ENABLE_TERMS_AND_CONDITIONS:
        from termsandconditions.models import UserTermsAndConditions
        UserTermsAndConditions.objects.filter(username=email).delete()

    # remove user options
    UserOptions.objects.filter(email=email).delete()

def get_should_delete_repo_ids(owned_repos, shared_out_repos, public_repos):
    """ Retrun repo id list that should been deleted.
    """

    shared_out_repo_ids = [repo.origin_repo_id if repo.is_virtual else repo.id
            for repo in shared_out_repos]
    public_repos_ids = [repo.id for repo in public_repos]

    # filter out public repos
    # filter out repos that repo/folder has been shared out
    should_delete_repo_ids = [repo.id for repo in owned_repos if repo.id
            not in shared_out_repo_ids + public_repos_ids]

    return should_delete_repo_ids

def get_repo_folder_share_info(shared_out_repos):
    """ Get repo share info.
    Return:
    [
        (repo_id, folder_path, permission, user_shared_to, group_id_shared_to),
        ...
    ]
    """

    repo_folder_share_info = []
    for repo in shared_out_repos:

        if not repo.is_virtual:
            # repo share to user
            if repo.share_type == 'personal':
                repo_folder_share_info.append((repo.id, '/', repo.permission, repo.user, None))

            # repo share to group
            if repo.share_type == 'group':
                repo_folder_share_info.append((repo.id, '/', repo.permission, None, repo.group_id))
        else:
            # folder share to user
            if repo.share_type == 'personal':
                repo_folder_share_info.append((repo.origin_repo_id, repo.origin_path, \
                        repo.permission, repo.user, None))

            # folder share to group
            if repo.share_type == 'group':
                repo_folder_share_info.append((repo.origin_repo_id, repo.origin_path, \
                        repo.permission, None, repo.group_id))

    return repo_folder_share_info


class Command(BaseCommand):

    help = "Read messages from alibaba message queue database table."

    def handle(self, *args, **options):

        random_second = randint(0, 60 * 10)
        time.sleep(random_second)

        messages = AlibabaMessageQueue.objects.filter(lock_version=0). \
                filter(is_consumed=0). \
                filter(topic=ALIBABA_MESSAGE_TOPIC_LEAVE_FILE_HANDOVER)

        for message in messages:

            self.stdout.write("\n\nStart for message %s.\n" % message.id)

            try:

                # get ccnet email
                leave_ccnet_email = get_leave_work_ccnet_email(message)
                super_ccnet_email = get_super_work_ccnet_email(message)
                if not leave_ccnet_email or not super_ccnet_email:
                    continue

                ccnet_user_obj = ccnet_api.get_emailuser(leave_ccnet_email)
                if not ccnet_user_obj:
                    continue

                # lock message
                AlibabaMessageQueue.objects.add_lock(message.id)

                actions_for_leave_worker(ccnet_user_obj)

                # the following is for delete/reshare repo/folder

                # get owned repos
                owned_repos = seafile_api.get_owned_repo_list(leave_ccnet_email)

                # get repos that repo/sub-folder has been shared out
                shared_out_repos = []
                shared_out_repos += seafile_api.get_share_out_repo_list(
                        leave_ccnet_email, -1, -1)
                shared_out_repos += seafile_api.get_group_repos_by_owner(
                        leave_ccnet_email)

                # get owned public repos
                public_repos = seafile_api.list_inner_pub_repos_by_owner(leave_ccnet_email)

                # delete repos that repo/sub-folder has NOT been shared to
                # user/group/public
                should_delete_repo_ids = get_should_delete_repo_ids(
                        owned_repos, shared_out_repos, public_repos)
                for repo_id in should_delete_repo_ids:
                    print '\ndelete repo %s' % repo_id
                    seafile_api.remove_repo(repo_id)

                # transfer repo to super
                # reshare repo public
                for repo in public_repos:
                    print '\ntransfer repo %s' % repo.id
                    seafile_api.set_repo_owner(repo.id, super_ccnet_email)
                    print 'reshare repo %s to public' % repo.id
                    seafile_api.add_inner_pub_repo(repo.id, repo.permission)

                # transfer repo to super
                # reshare repo/folder to user/group
                repo_folder_share_info = get_repo_folder_share_info(shared_out_repos)
                for info in repo_folder_share_info:

                    repo_id, folder_path, permission, to_user, to_group_id = info

                    # transfer repo
                    if seafile_api.get_repo_owner(repo_id) != super_ccnet_email:
                        print '\ntransfer repo %s' % repo_id
                        seafile_api.set_repo_owner(repo_id, super_ccnet_email)

                    repo = seafile_api.get_repo(repo_id)

                    print 'reshare repo/folder to user/group'
                    print info
                    if to_user:
                        if to_user == super_ccnet_email:
                            continue
                        share_dir_to_user(repo, folder_path, super_ccnet_email, \
                                super_ccnet_email, to_user, permission)

                    if to_group_id:
                        share_dir_to_group(repo, folder_path, super_ccnet_email, \
                                super_ccnet_email, to_group_id, permission)

                AlibabaMessageQueue.objects.mark_message_consumed(message.id)
            except Exception as e:
                print e

            AlibabaMessageQueue.objects.remove_lock(message.id)
