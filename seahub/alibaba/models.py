# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from __future__ import unicode_literals

import json

from django.db import models

ALIBABA_MESSAGE_QUEUE_TOPIC = '01-push_message'

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
    uid = models.CharField(max_length=64)
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

    def add_dingding_markdown_message(self, dingding_msg_title,
            dingding_msg_text, to_work_no_list):

        dingding_msg = {
            "msgtype": "markdown",
            "markdown": {
                "title": dingding_msg_title,
                "text": dingding_msg_text
            }
        }

        alibaba_message_body = {
            "pushType": "dingding",
            "content": dingding_msg,
            "pushWorkNos": to_work_no_list
        }

        AlibabaMessageQueue.objects.add_message(ALIBABA_MESSAGE_QUEUE_TOPIC,
                json.dumps(alibaba_message_body))

    def add_message(self, topic, message_body):

        message = self.model(topic=topic, message_body=message_body, lock_version=0)
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
