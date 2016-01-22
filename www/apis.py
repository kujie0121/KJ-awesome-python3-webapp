#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
JSON API definition: JSON API 定义，异常信息分类及处理。
'''

import json, logging, inspect, functools


#分页信息类：返回一个存储分页信息的str：
class Page(object):
    '''
    Page object for display pages.
    '''

    def __init__(self, item_count, page_index=1, page_size=10):
        '''
        Init Pagination by item_count, page_index and page_size.
        >>> p1 = Page(100, 1)
        >>> p1.page_count
        10
        >>> p1.offset
        0
        >>> p1.limit
        10
        >>> p2 = Page(90, 9, 10)
        >>> p2.page_count
        9
        >>> p2.offset
        80
        >>> p2.limit
        10
        >>> p3 = Page(91, 10, 10)
        >>> p3.page_count
        10
        >>> p3.offset
        90
        >>> p3.limit
        10
        '''
        self.item_count = item_count    #文章总数。
        self.page_size = page_size      #单页包含文章数，默认为10.
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)    #分页数。
        #page_index：页面索引，默认为1.
        #当文章总数为0或页面索引大于分页数，重置所有值：
        if (item_count == 0) or (page_index > self.page_count):
            self.offset = 0     #当前页面索引之前(已展示)的文章数。
            self.limit = 0      #单页文章最大量。
            self.page_index = 1     #页面索引
        else:
            self.page_index = page_index    #页面索引
            self.offset = self.page_size * (page_index - 1)     #当前页面索引之前(已展示)的文章数。
            self.limit = self.page_size     #单页文章最大量。

        self.has_next = self.page_index < self.page_count      #判断是否有下一页(小于分页数)。
        self.has_previous = self.page_index > 1         #判断是否有上一页(大于1)

    #重组页面参数信息为字符串：
    def __str__(self):
        return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s' % (self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

    __repr__ = __str__


#定义API异常基类：
class APIError(Exception):
    '''
    the base APIError which contains error(required), data(optional) and message(optional).
    '''
    #实例化基本属性：错误信息(必填)，数据(选填)，信息(选填)。
    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message

#定义输入值(有误、异常...)异常类：
class APIValueError(APIError):
    '''
    Indicate the input value has error or invalid. The data specifies the error field of input form.
    '''
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)

#定义资源未找到异常类：
class APIResourceNotFoundError(APIError):
    '''
    Indicate the resource was not found. The data specifies the resource name.
    '''
    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__('value:notfound', field, message)

#定义权限异常类：
class APIPermissionError(APIError):
    '''
    Indicate the api has no permission.
    '''
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)

