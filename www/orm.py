#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
ORM:对象关系映射
'''

import logging
import  asyncio, aiomysql

#打印SQL日志：
def log(sql, args=()):
    logging.info('SQL: %s' % sql)

#@asyncio.coroutine可以把一个 generator 标记为 coroutine 类型
#创建全局连接池，由全局变量__pool存储：
@asyncio.coroutine
def create_pool(loop, **kw):
    #打印创建数据库连接日志信息：
    logging.info('create database connection pool...')
    #声明'__pool'为全局变量：
    global __pool
    #aiomysql.create_pool()创建连接到Mysql数据库池中的协程链接：
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host', 'localhost'),           #数据库链接地址，默认localhost
        port=kw.get('port', 3306),                  #链接端口号，默认3306
        user=kw['user'],                            #登陆名
        password=kw['password'],                    #登陆密码
        db=kw['db'],                                #数据库名
        charset=kw.get('charset', 'utf8'),          #字符集设置，默认utf-8
        autocommit=kw.get('autocommit', True),      #自动提交模式，默认True
        maxsize=kw.get('maxsize', 10),              #最大连接数，默认10
        minsize=kw.get('minsize', 1),               #最小连接数，默认1
        loop=loop                                   #可选循环实例，[aiomysql默认为asyncio.get_event_loop()]
    )

#创建Select方法
@asyncio.coroutine
def select(sql, args, size=None):
    #打印SQL日志(查询调用时传递过来的sql语句和参数)：
    log(sql, args)
    global __pool
    with (yield from __pool) as conn:
        #创建游标字典：
        cur = yield from conn.cursor(aiomysql.DictCursor)
        #执行SQL语句；SQL语句的占位符是?，而MySQL的占位符是%s，需要进行处理:
        #execute(query, args=None)：query(str)-sql语句；args(list)-sql语句的替换参数列表(tuple或list)。
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        #根据size参数判断返回结果为指定组结果集还是全部结果结果集：
        if size:
            #返回指定的size组结果集：
            rs = yield from cur.fetchmany(size)
        else:
            #返回所有结果集：
            rs = yield from cur.fetchall()
        #关闭游标：
        yield from cur.close()
        #打印SQL执行结果日志：
        logging.info('rows returned: %s' % len(rs))
        return rs

#创建通用方法(insert，update，delete)，设置自动提交模式默认为True：
@asyncio.coroutine
def execute(sql, args, autocommit=True):
    log(sql)
    with (yield from __pool) as conn:
        try:
            cur = yield from conn.cursor()
            #SQL语句的占位符是?，而MySQL的占位符是%s:
            yield from cur.execute(sql.replace('?', '%s'), args)
            #返回执行后受影响的行的数量：
            affected = cur.rowcount
            yield from cur.close()
            #判断是否自动提交：
            if not autocommit:
                #提交事务(仅执行查询操作时可省略)：
                yield from conn.commit()
        except BaseException as e:
            if not autocommit:
                #有异常则回滚操作：
                yield from conn.rollback()
            raise
        return affected

#返回指定位参数格式的字符串，如'?, ?, ?':
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)

# 定义Field类，它负责保存数据库表的字段名和字段类型:
class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

#定义Field的各种Field子类:
#映射varchar的StringField：
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

#映射Boolean的BooleanField：
class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

#映射Integer的IntegerField：
class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

#映射Float的FloatField：
class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

#映射Text的TextField：
class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


#Model只是一个基类，通过元类metaclass：ModelMetaclass, 任何继承自Model的类（比如User）会自动通过ModelMetaclass扫描映射关系，并存储到自身的类属性(如__table__、__mappings__...)中, 可以将具体的子类User的映射信息读取出来：
class ModelMetaclass(type):
    #__new__(cls, *args, **kwargs) :创建对象时调用，返回当前对象的一个实例;注意：这里的第一个参数是cls即class本身.
    #__new__(当前准备创建的类的对象，类的名字，类继承的父类集合，类的方法集合)
    def __new__(cls, name, bases, attrs):
        # 排除Model类本身:
        if name=='Model':
            return type.__new__(cls, name, bases, attrs)
        # 获取table名称:
        tableName = attrs.get('__table__', None) or name
        #打印日志信息：
        logging.info('found model: %s (table: %s)' % (name, tableName))
        # 获取所有的Field(自己定义的类型)和主键名:
        mappings = dict()       #声明dict字典类型
        fields = []             #声明list类型
        primaryKey = None
        for k, v in attrs.items():      #dict.items()返回一个由tuple(包含key,value)组成的list。
            #判断attrs字典值是否为Field类型
            if isinstance(v, Field):
                #打印日志信息：
                logging.info('  found mapping: %s ==> %s' % (k, v))
                #填充attrs对值到mappings字典中：
                mappings[k] = v
                if v.primary_key:
                    # 找到主键:
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    #添加attrs字典中的key值到fields数组：
                    fields.append(k)
        if not primaryKey:
            raise RuntimeError('Primary key not found.')

        for k in mappings.keys():       #dict.keys()返回一个由key(字典的目录)值组成的list
            #删除attrs字典中对应的值(其实就是清空attrs字典)：
            attrs.pop(k)

        #将fields数组重新组合，在每个值上加了一对“ ` ` ”(shift+'~')符号，执行SQL语句时，如果表名、列名与mysql中的关键字重名，就必须用“ ` ` ”括起来：
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))    # map(函数，序列)：将传入的函数依次作用到序列的每个元素；
        #重新构造attrs字典：
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)


#定义所有ORM映射的基类Model，元类为ModelMetaclass:
#Model从dict继承，具备所有dict的功能，同时又实现了特殊方法__getattr__()和__setattr__()，因此又可以像引用普通字段那样引用(user['id'] = user.id)：
class Model(dict, metaclass = ModelMetaclass):
    #初始化已实例化后的所有父类对象，方便后续使用或扩展父类中的行为：
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

     #属性动态化处理；当使用点号获取类实例属性时，如果属性不存在就自动调用__getattr__方法。
    def __getattr__(self, key):     #此处为：提取字典内，指定key值的value，没找到则抛出异常：
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r'"model" object has no attribute "%s"' % key)

    #属性赋值；当设置类实例属性时自动调用。
    def __setattr__(self, key, value):      #此处为：设置字典对值。
        self[key] = value

    #提取字典内，指定key值的value，找不到时value为None：
    def getValue(self, key):
        #getattr(对象(Instance)，属性(name,字符串)，[default])：
        #如果对象中有属性，则返回该属性的值，相当于Instance.name，若没有则返回default值。
        return getattr(self, key, None)

    #提取字典内，指定key值的value，若为空则赋值为初始默认值：
    def getValueOrDefault(self, key):
        #获取字典内，指定key值的value，找不到时value为None：
        value = getattr(self, key, None)
        #若value值为None，则赋值为初始默认值：
        if value is None:
            field = self.__mappings__[key]  #获取对应key值的初始默认值
            if field.default is not None:
                #检查field.default对象是否可调用，若可调用则将返回值赋值给value，否则直接将对象field.default赋值给value：
                value = field.default() if callable(field.default) else field.default
                #打印使用默认值日志：
                logging.debug('using default value for %s: %s' % (key, str(value)))
                #将value赋值给实例的属性key；也就是 self.key=value:
                setattr(self, key, value)
        return  value


#-------------往Model类添加class方法，就可以让所有子类调用class方法：---------------#
    #classmethod是用来指定一个类的方法为类方法，没有此参数指定的类的方法为实例方法，类方法既可以直接类调用(C.f())，也可以进行实例调用(C().f())。：
    #所有这些方法都用@asyncio.coroutine装饰，变成一个协程:

    #实现条件查询：返回所有结果的list，结果为空返回None：
    @classmethod
    @asyncio.coroutine
    def findAll(cls, where=None, args=None, **kw):
        ' find objects by where clause. '
        #创建sql数组：
        sql = [cls.__select__]
        #将查询条件添加到sql数组中：
        if where:
            sql.append('where')
            sql.append(where)
        #如果args为空，则将它声明为空list
        if args is None:
            args = []
        #获取查询条件orderBy(分组)参数，若没有则为None
        orderBy = kw.get('orderBy', None)
        #若orderBy参数不为None，则添加到sql数组：
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        #获取查询条件limit(分页)参数，若没有则为None
        limit = kw.get('limit', None)
        #若limit参数不为None，则添加到sql数组：
        if limit is not None:
            sql.append('limit')
            #判断limit参数类型来设置对应的替换符串('？')：
            if isinstance(limit, int):
                #mysql中limit参数如果只给定一个参数，它表示返回最大的记录行数目：
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                #mysql中limit参数如果给两个参数，分别表示返回查询记录的起始行数目和最大记录行数目：
                sql.append('?, ?')
                args.extend(limit)
            #若不满足以上两种类型，则参数有误，抛出异常：
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        #调用select()实现对数据库进行select操作：
        rs = yield from select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    #实现条件查询：返回单个结果，结果为空返回None：
    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        #构建sql数组：'_num_' 为自定义sql查询结果列名
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        #将查询条件添加到sql数组中：
        if where:
            sql.append('where')
            sql.append(where)
            #调用select()实现对数据库进行select操作：
        rs = yield from select(' '.join(sql), args, 1)  #将sql数组拼接成sql语句
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    #实现主键查询：返回单个对象，若结果为空返回None：
    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        ' find object by primary key. '
        #调用select()实现对数据库进行select操作：
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])


#-------------往Model类添加实例方法，就可以让所有子类调用实例方法：---------------#
    #所有这些方法都用@asyncio.coroutine装饰，变成一个协程:

    #实现数据插入：
    @asyncio.coroutine
    def save(self):
        #构建args属性值(__fields__不包括主键)list，没有的则赋值为初始默认值：
        args = list(map(self.getValueOrDefault, self.__fields__))
        #增加主键值到args中，没有则赋值为初始默认值：
        args.append(self.getValueOrDefault(self.__primary_key__))
        #调用execute()实现对数据库进行insert操作：
        rows = yield from execute(self.__insert__, args)    #返回受影响行数
        if rows != 1:
            #若返回值不等于1，则打印日志：
            logging.warn('failed to insert record: affected rows: %s' % rows)

    #实现数据更新：
    @asyncio.coroutine
    def update(self):
        #构建args属性值(__fields__不包括主键)list，找不到时value为None：
        args = list(map(self.getValue, self.__fields__))
        #增加主键值到args中，找不到时value为None：
        args.append(self.getValue(self.__primary_key__))
        #调用execute()实现对数据库进行update操作：
        rows = yield from execute(self.__update__, args)
        if rows != 1:
            #若返回值不等于1，则打印日志：
            logging.warn('failed to update by primary key: affected rows: %s' % rows)

    #实现数据删除：
    @asyncio.coroutine
    def remove(self):
        #构建args属性值(主键)list，找不到时value为None：
        args = [self.getValue(self.__primary_key__)]
        #调用execute()实现对数据库进行delete操作：
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            #若返回值不等于1，则打印日志：
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)
