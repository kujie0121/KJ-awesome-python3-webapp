#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Model: Models for user, blog, comment.
'''

import time, uuid

from orm import Model, StringField, BooleanField, FloatField, TextField

#使用时间戳和UUID库结合生成唯一ID：
def next_id():
    #uuid4()——基于随机数：由伪随机数得到，有一定的重复概率，该概率可以计算出来。
    #hex()：转换一个整数对象为十六进制的字符串。
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

#用户：
class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)

#文章：
class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)

#评论：
class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)
