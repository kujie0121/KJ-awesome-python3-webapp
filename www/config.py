#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Configuration
'''

import config_default

#重新定义一个Dict类，继承自dict：
class Dict(dict):
    '''
    Simple dict but support access as x.y style.
    '''
    #初始化已实例化后的所有父类对象，方便后续使用或扩展父类中的行为：
    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)
        #zip([seql, ...])接受一系列可迭代对象作为参数，将对象中对应的元素打包成一个个tuple（元组），然后返回由这些tuples组成的list（列表）。
        # 若传入参数的长度不等，则返回list的长度和参数中长度最短的对象相同。
        for k, v in zip(names, values):
            self[k] = v
    #属性动态化处理；当使用点号获取类实例属性时，如果属性不存在就自动调用__getattr__方法。
    def __getattr__(self, key):     #此处为：提取字典内，指定key值的value，没找到则抛出异常。
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    #属性赋值；当设置类实例属性时自动调用。
    def __setattr__(self, key, value):      #此处为：设置字典对值。
        self[key] = value

#将override字典中的对应值覆盖到defaults字典：
def merge(defaults, override):
    r = {}
    for k, v in defaults.items():       #dict.items()返回一个由tuple(包含key,value)组成的list。
        #若override字典中包含defaults.key，则替换对应的defaults.value为override.value。
        if k in override:
            #判断v是否为”dict“类型：
            if isinstance(v, dict):
                #递归函数：
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        else:
            r[k] = v
    return r

#字典转换，将dict字典类型转换成自定义的Dict类型：
def toDict(d):
    D = Dict()
    for k, v in d.items():      #dict.items()返回一个由tuple(包含key,value)组成的list。
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D

configs = config_default.configs

#使用生产配置信息替换开发配置信息：
try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

configs = toDict(configs)