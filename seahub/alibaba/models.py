# encoding: utf-8

# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from __future__ import unicode_literals

import json
import uuid

from django.db import models

try:
    from seahub.settings import ALIBABA_MESSAGE_TOPIC_NOTICE, \
            ALIBABA_DINGDING_TALK_URL
except ImportError:
    ALIBABA_MESSAGE_TOPIC_NOTICE = '01_push_message'
    ALIBABA_DINGDING_TALK_URL = "dingtalk://dingtalkclient/page/link?url=%s&pc_slide=false"

class AlibabaProfileManager(models.Manager):

    def get_profile(self, email):
        try:
            profile = super(AlibabaProfileManager, self).get(uid=email)
        except AlibabaProfile.DoesNotExist:
            return None

        return profile

    def get_profile_by_work_no(self, work_no):
        try:
            profile = super(AlibabaProfileManager, self).get(work_no=work_no)
        except AlibabaProfile.DoesNotExist:
            return None

        return profile


class AlibabaProfile(models.Model):
    id = models.BigAutoField(primary_key=True)
    uid = models.CharField(max_length=191, unique=True)
    personal_photo_url = models.CharField(max_length=225, blank=True, null=True)
    person_id = models.BigIntegerField(unique=True)
    emp_name = models.CharField(max_length=64, blank=True, null=True)
    pinyin_name = models.CharField(max_length=64, blank=True, null=True)
    nick_name = models.CharField(max_length=64, blank=True, null=True)
    pinyin_nick = models.CharField(max_length=64, blank=True, null=True)
    work_no = models.CharField(max_length=16)
    post_name = models.CharField(max_length=64)
    post_name_en = models.CharField(max_length=64)
    dept_name = models.CharField(max_length=128)
    dept_name_en = models.CharField(max_length=128)
    work_status = models.CharField(max_length=4)
    gmt_leave = models.DateTimeField(blank=True, null=True)

    objects = AlibabaProfileManager()

    class Meta:
        managed = False
        db_table = 'alibaba_profile'


class AlibabaMessageQueueManager(models.Manager):

    def add_dingding_message(self, alibaba_message_topic,
            content_cn, content_en, to_work_no_list):

        message_body = {
            "pushType": "dingding",
            "contentCN": content_cn,
            "contentEN": content_en,
            "pushWorkNos": to_work_no_list
        }

        message_body_json = json.dumps(message_body,
                ensure_ascii=False, encoding='utf8')

        message = self.model(topic=alibaba_message_topic,
                message_body=message_body_json,
                lock_version=0, is_consumed=0,
                message_key=uuid.uuid4())

        message.save(using=self._db)
        return message


class AlibabaMessageQueue(models.Model):
    id = models.BigAutoField(primary_key=True)
    topic = models.CharField(max_length=64)
    gmt_create = models.DateTimeField()
    gmt_modified = models.DateTimeField()
    message_body = models.TextField()
    is_consumed = models.IntegerField(blank=True, null=True)
    lock_version = models.IntegerField()
    message_key = models.CharField(max_length=128, blank=True, null=True)

    objects = AlibabaMessageQueueManager()

    class Meta:
        managed = False
        db_table = 'message_queue'
