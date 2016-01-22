#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
URL处理器
'''

import re, time, json, logging, hashlib, base64, asyncio

from aiohttp import web

#导入markdown2.py文件
import markdown2
#导入coroweb.py文件
from coroweb import get, post
#导入models.py文件
from models import User, Comment, Blog, next_id
#导入apis.py文件
from apis import APIError, APIValueError, APIResourceNotFoundError, APIPermissionError, Page
#导入config.py文件
from config import configs


COOKIE_NAME = 'awesession'
#配置文件中对应的信息：
_COOKIE_KEY = configs.session.secret

#权限校验：
def check_admin(request):
    #若用户属性为空或用户权限不正常，抛出权限异常：
    if request.__user__ is None or request.__user__.admin:      #__user__.admin：admin属性为用户注册时赋予的(默认False)，存储在数据库。
        raise APIPermissionError()

#获取页面索引；将str类型转化为int类型，并校验索引合法性：
def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

#text格式转换成html格式：
def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)


#计算加密cookie；将用户信息构造成cookie信息：
def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

#解析cookie处理器；
@asyncio.coroutine      #@asyncio.coroutine装饰，变成一个协程:
def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    #若cookie信息为空在返回None：
    if not cookie_str:
        return None
    try:
        #将cookie信息按照‘-’进行切片处理：
        L = cookie_str.split('-')
        #若切片数组长度不为3，则返回None：
        if len(L) != 3:
            return None
        #分别取到uid，cookie有效期，用户信息摘要值：
        uid, expires, sha1 = L
        #若cookie有效期小于当前时间，则返回None：
        if int(expires) < time.time():
            return None
        #根据uid在数据库中查询对应的用户信息：
        user = yield from User.find(uid)
        #查询结果为空，则返回None：
        if user is None:
            return None
        #重组用户信息并计算SHA1摘要值，同cookie中的用户信息摘要值比对：
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            #打印(无效SHA1摘要值)日志：
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None


#基础页 URL处理函数：
@get('/')
def index(*, page='1'):
    #获取页面索引，默认为1；因为首页默认索引页为1，其实这里没用上：
    page_index = get_page_index(page)
    #获取数据库中的文章总数：
    num = yield from Blog.findNumber('count(id)')
    page = Page(num, page_index)
    if num == 0:
        blogs = []
    else:
        #查询数据库中Blog表中对应分页的文章结果；(limit为mysql的分页查询条件)
        blogs = yield from Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        '__template__': 'blogs.html',
        'page': page,
        'blogs': blogs
    }

#指定内容页 URL处理函数：
@get('/blog/{id}')
def get_blog(id):
    #通过id在数据库Blog表中查询对应内容：
    blog = yield from Blog.find(id)
    #通过id在数据库Comment表中查询对应内容：
    comments = yield from Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        #将content值从text格式转换成html格式：
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }

#用户注册 URL处理函数：
@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }

#用户登陆 URL处理函数：
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

#用户注销 URL处理函数：
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

#管理中心 URL处理函数：
@get('/manage/')
def manage():
    return 'redirect:/manage/comments'    #重定向到执行URL。

#内容(博客)管理 URL处理函数：
@get('/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }

#创建内容(博客) URL处理函数：
@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }

#修改内容(博客) URL处理函数：
@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/%s' % id
    }

#评论管理 URL处理函数：
@get('/manage/comments')
def manage_comments(*, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page)
    }

#全部用户管理 URL处理函数：
@get('/manage/users')
def manage_users(*, page='1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page)
    }

#指定索引页评论展示 URL处理函数：
@get('/api/comments')
def api_comments(*, page='1'):
    #获取页面索引，默认为1：
    page_index = get_page_index(page)
    #查询数据库中Comment表中评论总数：
    num = yield from Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = yield from Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)

#指定内容(博客)展示 URL处理函数：
@get('/api/blogs/{id}')
def api_get_blog(*, id):
    blog = yield from Blog.find(id)
    return blog

#指定索引页内容(博客)展示 URL处理函数：
@get('/api/blogs')
def api_blogs(*, page='1'):
    #获取页面索引，默认为1：
    page_index = get_page_index(page)
    #查询数据库中Blog表中文章总数：
    num = yield from Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    #查询数据库中Blog表中对应分页的文章结果；(limit为mysql的分页查询条件)
    blogs = yield from Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

#指定索引页用户管理 URL处理函数：
@get('/api/users')
def api_get_users(*, page='1'):
    #获取页面索引，默认为1：
    page_index = get_page_index(page)
    #查询数据库中User表中用户总数：
    num = yield from User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    #查询数据库中User表中对应分页的用户结果；(limit为mysql的分页查询条件)
    users = yield from User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)

#用户登陆信息校验 URL处理函数；校验用户登陆信息并返回一个带COOKIE信息的响应流：
@post('/api/authenticate')
def authenticate(*, email, passwd):
    #判断email(用户名)及password是否为空；为空则抛出异常：
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')
    #数据中查询对应的email信息：
    users = yield from User.findAll('email=?', [email])
    #判断查询结果是否存在，若不存在则抛出异常：
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    #获取查询结果集的第一条数据：
    user = users[0]
    # check passwd:
    #调用摘要算法SHA1组装登陆信息；计算摘要值同数据库中的信息进行比配：
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        #登陆信息不匹配则跑出异常：
        raise APIValueError('passwd', 'Invalid password.')
    # authenticate ok, set cookie:
    #构造session cookie信息：
    r = web.Response()
    #aiohttp.web.StreamResponse().set_cookie()：设置cookie的方法。
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    #以json格式序列化响应信息； ensure_ascii默认为True，非ASCII字符也进行转义。如果为False，这些字符将保持原样。
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

#email 格式正则表达式：
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
#password 格式正则表达式：
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

#用户注册信息保存 URL处理函数；保存用户信息到数据库并返回一个带COOKIE信息的响应流：
@post('/api/users')
def api_register_user(*, email, name, passwd):
    #判断name是否为空：
    if not name or not name.strip():
        raise APIValueError('name')
    #判断email是否为空及是否满足email格式：
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    #判断password首付为空及是否满足password格式：
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    #数据中查询对应的email信息：
    users = yield from User.findAll('email=?', [email])
    #判断查询结果是否存在，若存在则返回异常提示邮件已存在：
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    #生成唯一ID：
    uid = next_id()
    #重构唯一ID和password成新的字符串：
    sha1_passwd = '%s:%s' % (uid, passwd)
    #构建用户对象信息：
    #hashlib.sha1().hexdigest():取得SHA1哈希摘要算法的摘要值。
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    #将用户信息存储到数据库：
    yield from user.save()
    # make session cookie:
    #构造session cookie信息：
    r = web.Response()
    #aiohttp.web.StreamResponse().set_cookie()：设置cookie的方法。
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)   #max_age：定义cookie的有效期(秒)；
    user.passwd = '******'
    r.content_type = 'application/json'
    #以json格式序列化响应信息； ensure_ascii默认为True，非ASCII字符也进行转义。如果为False，这些字符将保持原样。
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

#创建内容(博客)保存 URL处理函数：返回Blog实例：
@post('/api/blogs')
def api_create_blog(request, *, name, summary, content):
    #校验当前用户权限：
    check_admin(request)
    #校验传递值中参数‘name’是否为空或空串,为空则抛出异常：
    if not name or not name.strip():
        #参数‘name’为空则抛出异常：
        raise APIValueError('name', 'name cannot be empty.')
    #校验传递值中参数‘summary’是否为空或空串,为空则抛出异常：
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    #校验传递值中参数‘content’是否为空或空串,为空则抛出异常：
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    #创建Blog实例：
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    #将Blog信息存储到数据库：
    yield from blog.save()
    return blog

#更新内容(博客) URL处理函数：返回Blog实例：
@post('/api/blogs/{id}')
def api_update_blog(id, request, *, name, summary, content):
    #校验当前用户权限：
    check_admin(request)
    #数据库Blog表中查询指定文章信息：
    blog = yield from Blog.find(id)
    #校验传递值中参数‘name’是否为空或空串,为空则抛出异常：
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    #校验传递值中参数‘summary’是否为空或空串,为空则抛出异常：
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    #校验传递值中参数‘content’是否为空或空串,为空则抛出异常：
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    #将传递值中的信息赋值到blog实例中：
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    #将Blog信息更新到数据库：
    yield from blog.update()
    return blog

#删除内容(博客) URL处理函数：返回id信息dict：
@post('/api/blogs/{id}/delete')
def api_delete_blog(request, *, id):
    #校验当前用户权限：
    check_admin(request)
    #数据库Blog表中查询指定文章信息：
    blog = yield from Blog.find(id)
    #将Blog信息从数据库删除：
    yield from blog.remove()
    return dict(id=id)

#创建评论 URL处理函数：返回Comment实例：
@post('/api/blogs/{id}/comments')
def api_create_comment(id, request, *, content):
    #获取请求中的用户信息：
    user = request.__user__
    #用户信息为None则抛出异常：
    if user is None:
        raise APIPermissionError('Please signin first.')
    #参数中内容信息为空，抛出异常：
    if not content or not content.strip():
        raise APIValueError('content')
    #数据库Blog表中查询指定文章信息：
    blog = yield from Blog.find(id)
    #查询无结果则抛出异常：
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    #创建comment实例：
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
    #将Comment信息存储到数据库：
    yield from comment.save()
    return comment

#删除评论 URL处理函数：返回id信息dict：
@post('/api/comments/{id}/delete')
def api_delete_comments(id, request):
    #校验当前用户权限：
    check_admin(request)
    #数据库Comment表中查询指定评论信息：
    c = yield from Comment.find(id)
    #查询无结果则抛出异常：
    if c is None:
        raise APIResourceNotFoundError('Comment')
    #将Comment信息从数据库删除：
    yield from c.remove()
    return dict(id=id)