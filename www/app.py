#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Http服务器
'''

import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web     #aiohttp.web 会自动创建 Request实例。
from jinja2 import Environment, FileSystemLoader

#导入config.py文件
from config import configs

#导入orm.py文件
import orm
#导入coroweb.py文件
from coroweb import add_routes, add_static
#导入handlers.py文件
from handlers import cookie2user, COOKIE_NAME




#使用jinja2模块为app添加 env环境对象：
def init_jinja2(app, **kw):
    #打印日志：
    logging.info('init jinja2...')
    #获取方法传递参数并重组成新的参数dict：
    options = dict(
        autoescape = kw.get('autoescape', True),        #dict.get(key, default=None)：返回指定键的值，如果值不在字典中返回默认值None。
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        #os.path.abspath(__file__)：返回当前脚本的绝对路径(包括文件名)。
        #os.path.dirname()：去掉文件名，返回目录路径。
        #os.path.join():将分离的各部分组合成一个路径名。
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    #打印(设置jinja2模板路径)日志：
    logging.info('set jinja2 template path: %s' % path)
    #jinja2.Environment()：创建模板环境和在指定文件夹中寻找模板的加载器。
    #jinja2.FileSystemLoader()：从文件系统加载模板。
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)   #环境的过滤器字典。
    #若过滤器不为None，将过滤器字典值循环出来并添加到新的env环境对象的过滤器字典中：
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env


#middlewares请求响应处理器-日志处理器：
#记录URL日志：
@asyncio.coroutine      #@asyncio.coroutine装饰，变成一个协程:
def logger_factory(app, handler):
    @asyncio.coroutine
    def logger(request):
        #不需要手动创建 Request实例 - aiohttp.web 会自动创建。
        #打印(请求方法及地址)日志：
        logging.info('Request: %s %s' % (request.method, request.path))
        # yield from asyncio.sleep(0.3)
        return (yield from handler(request))
    return logger

#middlewares请求响应处理器-cookie解析处理器：
@asyncio.coroutine      #@asyncio.coroutine装饰，变成一个协程:
def auth_factory(app, handler):
    @asyncio.coroutine
    def auth(request):
        #不需要手动创建 Request实例 - aiohttp.web 会自动创建。
        #打印(请求方法，请求路径)日志：
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            #根据COOKIE名解析对应cookie；
            user = yield from cookie2user(cookie_str)
            #解析cookie信息不为空则赋值到request.__user__：
            if user:
                #打印(设置当前用户信息)日志：
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        #请求路径以‘/manage/’开头，且cookie用户信息不为空或cookie用户权限是否为管理员权限：
        if request.path.startswith('/manage/') and (request.__user__ is None or request.__user__.admin):
            return web.HTTPFound('/signin')

        return (yield from handler(request))
    return auth


#middlewares请求响应处理器-数据处理器：
@asyncio.coroutine      #@asyncio.coroutine装饰，变成一个协程:
def data_factory(app, handler):
    @asyncio.coroutine
    def parse_data(request):
        #判断请求方法是否为POST类型：
        if request.method == 'POST':
            #判断POST请求的实体MIME类型：
            if request.content_type.startswith('application/json'):
                #request.json() 是个协程。
                request.__data__ = yield from request.json()    #以JSON编码读取请求内容：
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                #request.post() 是个协程。
                request.__data__ = yield from request.post()    #读取请求内容的POST参数：
                logging.info('request form: %s' % str(request.__data__))
        return (yield from handler(request))
    return parse_data

#middlewares请求响应处理器-响应处理器：
#把返回值转换为web.Response 对象再返回，以保证满足aiohttp的要求：
@asyncio.coroutine      #@asyncio.coroutine装饰，变成一个协程:
def response_factory(app, handler):
    @asyncio.coroutine
    def response(request):
        logging.info('Response handler... ')
        r = yield from handler(request)

        #判断是否为“HTTP响应处理”类型，True则返回：
        if isinstance(r, web.StreamResponse):
            return r
        #判断是否为“bytes”类型：
        if isinstance(r, bytes):
            #aiohttp.web.Response()：继承自StreamResponse；接收参数来设置HTTP响应体。
            resp = web.Response(body=r)
            #设置实体MIME类型：
            resp.content_type = 'application/octet-stream'
            return resp
        #判断是否为“string”类型：
        if isinstance(r, str):
            #判断是否以'redirect:'开头：
            if r.startswith('redirect:'):       #redirect：重定向，服务器返回‘302’代码.
                #切片处理r；返回重定向结果：
                return web.HTTPFound(r[9:])
            #不是以'redirect:'开头，则进行如下处理并返回：
            #aiohttp.web.Response()：继承自StreamResponse；接收参数来设置HTTP响应体。
            resp = web.Response(body=r.encode('utf-8'))     #encode()：转换成指定编码类型(一般情况是转换Unicode编码)。
            #设置实体MIME类型：
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        #判断是否为“dict”类型：
        if isinstance(r, dict):
            #获取字典中的env环境对象：
            template = r.get('__template__')
            #判断env环境对象是否为None：
            if template is None:
                #json.dumps()：以JSON编码格式转换python对象，返回一个str。“ensure_ascii=False”：非ASCII字符不转换，原样输出。
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                #设置实体MIME类型：
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                #取出cookie用户信息绑定到request对象：
                r['__user__'] = request.__user__
                #jinja2.Environment.get_template()：加载指定模板。
                #jinja2.Template.render()：返回模板unicode字符串。
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        #判断是否为“int”类型且 100<= r <600，直接返回r：
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        #判断是否为“tuple”类型且 tuple长度为2：
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            #判断tuple[0]是否为“int”类型且 100<= tuple[0] <600：
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))

        #以上条件都未满足，默认的返回值resp赋值方式：
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

#时间日期 过滤器；将浮点类型的日期时间转换成日期时间字符串：
#created_at渲染出来的是一个浮点数，通过jinja2的 filter（过滤器），把一个浮点数转换成日期字符串。初始化jinja2时设置。
def datetime_filter(t):
    #time.time()：返回当前时间的时间戳(1970后经过的秒数)，浮点类型。
    delta = int(time.time() - t)    #获取时间差。
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    #datetime.fromtimestamp(timestamp)：返回平台的本地日期时间对象.
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


#@asyncio.coroutine把一个generator标记为coroutine类型，然后把这个coroutine扔到EventLoop中执行：
@asyncio.coroutine
def init(loop):
    #orm.create_pool()创建数据库连接：
    yield from orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='root', password='', db='awesome')
    #创建 middlewares 请求响应处理器(字典类型)对象，可以通过‘请求处理程序’返回对应数据：
    app = web.Application(loop=loop, middlewares=[
        logger_factory, auth_factory, response_factory
    ])
    #初始化jinja2模板，添加filter(过滤器)：
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    #'handelers'模块自动注册,也就是取代aiohttp.web.UrlDispatcher.add_route()单个增加响应规则：
    add_routes(app, 'handlers')
    #aiohttp.web.UrlDispatcher.add_route():增加响应规则；即设置请求条件(请求方式，地址等...)和对应的处理程序：
    #app.router.add_route('GET', '/', index)
    #给文件添加静态地址：
    add_static(app)

    #loop.create_server()利用asyncio创建TCP服务：
    #make_handler()创建HTTP协议处理器来处理请求：
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    #打印日志信息：
    logging.info('server started at http://127.0.0.1:9000...')
    return srv



# 获取EventLoop:
loop = asyncio.get_event_loop()
# 执行coroutine(协程)：
loop.run_until_complete(init(loop))
#持续运行直到调用停止命令：
loop.run_forever()
