#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Default configurations.
开发环境配置信息：
'''

configs = {
    'debug': True,
    'db': {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '',
        'db': 'awesome'
    },
    'session': {
        'secret': 'Awesome'
    }
}