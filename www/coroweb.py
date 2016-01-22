#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
WEB框架：
'''

import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web     #aiohttp.web 会自动创建 Request实例。

from apis import APIError

#定义get装饰器；这样，一个函数通过@get()的装饰就附带了URL信息。
def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

#定义post装饰器；这样，一个函数通过@post()的装饰就附带了URL信息。
def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

#获取函数传递值中的可变参数或命名关键字参数(不包含设置缺省值的)名称列表：
def get_required_kw_args(fn):
    args = []
    #inspect.signature(fn)：表示fn函数的调用签名及其返回注释，为函数提供一个Parameter对象存储参数集合。
    #inspect.signature(fn).parameters：参数名与参数对象的有序映射。
    params = inspect.signature(fn).parameters
    for name, param in params.items():  #.items()返回一个由tuple(此处包含name, parameters object)组成的list。
        #inspect.Parameter.kind：描述参数值对应到传参列表(有固定的5种方式，KEYWORD_ONLY表示值为“可变参数或命名关键字参数”)的方式。
        #inspect.Parameter.default：参数的缺省值，如果没有则属性被设置为 Parameter.empty。
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

#获取函数传递值中的可变参数或命名关键字参数(全部的)名称列表：
def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

#判断函数传递值中是否存在可变参数或命名关键字参数：
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

#判断函数传递值中是否存在关键字参数：
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        #VAR_KEYWORD表示值为关键字参数。
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

#判断函数传递值中是否包含“request”参数，若有则返回True：
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        #传递值中包含名为'request'的参数则跳出本次循环(不执行本次循环中的后续语句，但还是接着for循环)，found赋值为True：
        if name == 'request':
            found = True
            continue
        #VAR_POSITIONAL表示值为可变参数。
        #传递值中包含参数名为'request'的参数，且参数值对应到传参列表方式不是“可变参数、关键字命名参数、关键字参数”中的任意一种，则抛出异常：
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

#aiohttp.web的request handler实例，当url地址请求的时候就会调用。
#封装一个URL处理函数类，由于定义了__call__()方法，因此可以将其实例视为函数：
class RequestHandler(object):
    #不需要手动创建 Request实例 - aiohttp.web 会自动创建。
    #初始化已实例化后的所有父类对象，方便后续使用或扩展父类中的行为：
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)     #判断函数传递值中是否包含“request”参数，若有则返回True。
        self._has_var_kw_arg = has_var_kw_arg(fn)       #判断函数传递值中是否存在关键字参数。
        self._has_named_kw_args = has_named_kw_args(fn) #判断函数传递值中是否存在可变参数或命名关键字参数。
        self._named_kw_args = get_named_kw_args(fn)     #获取函数传递值中的可变参数或命名关键字参数(全部的)名称列表。
        self._required_kw_args = get_required_kw_args(fn)   #获取函数传递值中的可变参数或命名关键字参数(不包含设置缺省值的)名称列表。

    #@asyncio.coroutine装饰，变成一个协程:
    @asyncio.coroutine
    def __call__(self, request):    #Request 实例为 aiohttp.web 自动创建的。
        kw = None
        #判断函数是否包含“可变参数、命名关键字参数、关键字参数”，以及是否能获取到参数(不包含缺省)名称列表：
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            #判断HTTP请求方法使用的类型：
            if request.method == 'POST':
                #Contern-Type 标明发送或者接收的实体的MIME类型。例如：Content-Type: text/html
                #判断POST请求的实体MIME类型是否存在：
                if not request.content_type:
                    #MIME类型不存在则返回错误信息：
                    return web.HTTPBadRequest('Missing Content-Type.')
                #将POST请求的实体MIME类型值转换为全小写格式：
                ct = request.content_type.lower()
                #str.startswith(str,[strbeg(int)],[strend(int)]):检查字符串是否是以指定子字符串开头，返回True/False。若参数 beg 和 end 指定值，则在指定范围内检查。
                #检查“content_type”类型是否为“application/json”开头的字符串类型：
                if ct.startswith('application/json'):
                    #以JSON编码读取请求内容：
                    params = yield from request.json()  #request.json() 是个协程。
                    #判断读取的内容是否为“dict”类型；JSON的“object”类型对应的是python中的“dict”类型。
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                #检查“content_type”类型是否为“application/x-www-form-urlencoded”或“multipart/form-data”开头的字符串类型：
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    #读取请求内容的POST参数：
                    params = yield from request.post()  #request.post() 是个协程。
                    #构造POST参数字典：
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            #判断HTTP请求方法使用的类型：
            if request.method == 'GET':
                #获取请求URL中的查询字符串；如：“id=10”。
                qs = request.query_string
                if qs:
                    kw = dict()
                    #urllib.parse.parse_qs(str)：返回解析指定字符串中的查询字符串数据字典；可选参数值“True”表示空白值保留为空白字符串，默认为忽略(False)。
                    #循环出查询字符串数据字典并重组：
                    for k, v in parse.parse_qs(qs, True).items():   #dict.items()返回一个由tuple(包含key,value)组成的list。
                        kw[k] = v[0]
        if kw is None:
            #request.match_info：地址解析的(只读属性和抽象匹配信息实例)结果；确切的类型的属性取决于所使用的地址类型。
            kw = dict(**request.match_info)

        else:
            #若函数不包含“关键字参数”且可变参数或命名关键字参数(全部的)名称列表不为空，则执行以下操作：
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                #循环出参数名称列表并重组成字典：
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            #循环出地址解析的结果字典数据并更新值到kw字典：
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    #打印日志：
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        #判断函数传递值中是否包含“request”参数：若包含则添加至kw字典：
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        #获取函数传递值中的可变参数或命名关键字参数(不包含设置缺省值的)名称列表。
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    #传递值的参数不存在于kw字典则返回错误信息：
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        #打印(调用函数的参数字典)日志：
        logging.info('call with args: %s' % str(kw))
        try:
            #使用重构的kw参数字典，执行函数并返回结果：
            r = yield from self._func(**kw)
            return r
        except APIError as e:
            #返回自定义的异常信息分类及处理信息：
            return dict(error=e.error, data=e.data, message=e.message)

#添加静态地址的处理函数：
def add_static(app):
    #os.path.abspath(__file__)：返回当前脚本的绝对路径(包括文件名)。
    #os.path.dirname()：去掉文件名，返回目录路径。
    #os.path.join():将分离的各部分组合成一个路径名。
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    #aiohttp.web.Application.router: 返回地址实例属性(只读)。
    #aiohttp.web.UrlDispatcher.add_static(prefix, path)-prefix：URL地址前缀；给返回的静态文件添加地址和处理程序，返回新的静态地址实例。
    app.router.add_static('/static/', path)
    #打印(添加静态地址信息)日志：
    logging.info('add static %s => %s' % ('/static/', path))

#用来注册一个URL的处理函数：
def add_route(app, fn):
    #getattr(对象(Instance)，属性(name,字符串)，[default])：
    #如果对象中有属性，则返回该属性的值，相当于Instance.name，若没有则返回default值。
    method = getattr(fn, '__method__', None)    #获取请求方式。
    path = getattr(fn, '__route__', None)       #获取地址信息。
    #若请求方式或地址信息为None则抛出异常：
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    #判断函数是否为协程函数且为生成器函数：
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        #若不是协程函数(生成器函数)，则将其装饰成协程函数：
        fn = asyncio.coroutine(fn)
    #inspect.signature(fn)：返回fn函数的参数对象；inspect.signature(fn).parameters：返回包含fn函数的参数映射的字典对象。
    #打印添加地址的日志信息：
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))     #dict.keys()返回一个由key(字典的目录)值组成的list
    #aiohttp.web.Application.router: 返回地址实例属性(只读)。
    #aiohttp.web.UrlDispatcher.add_route(method, path, handler):给地址增加响应规则；即设置请求条件(请求方式，地址等...)和对应的处理程序，返回新的绝对地址或动态地址。
    app.router.add_route(method, path, RequestHandler(app, fn))

#自动扫描；自动把handler模块的所有符合条件的函数注册了:
def add_routes(app, module_name):
    #str.rfind(str):返回字符串最后一次出现的位置，如果没有匹配项则返回-1。
    n = module_name.rfind('.')
    if n == (-1):
        #没有匹配项，则导入“module_name”模块：
        mod = __import__(module_name, globals(), locals())
    else:
        #切片：
        name = module_name[n+1:]    #此处就是取“module_name”参数的最后一个“.”之后的字符串。
        #“__import__(module_name[:n], globals(), locals(), [name])”：等价于 “from module_name[:n] import name”
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    #dir()：不带参数时，返回当前范围内的变量、方法和定义的类型列表；带参数时，返回参数的属性、方法列表。
    for attr in dir(mod):
        #参数以“_”开头的，后边的语句不执行，接着for循环：
        if attr.startswith('_'):
            continue
        #此处相当于：fn = mod.attr：
        fn = getattr(mod, attr)
        #检查对象fn是否可调用：
        if callable(fn):
            #getattr(对象(Instance)，属性(name,字符串)，[default])：
            #如果对象中有属性，则返回该属性的值，相当于Instance.name，若没有则返回default值。
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            #如果method和path不为None，就执行注册URL的处理函数：
            if method and path:
                add_route(app, fn)
