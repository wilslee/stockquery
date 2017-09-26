# coding: utf-8
import hashlib
import os
import datetime
import urllib.parse
import psycopg2
from flask import (Flask, render_template, request, g, session,
redirect, url_for, abort)
from wechatpy import parse_message, create_reply
from wechatpy.utils import check_signature
from wechatpy.exceptions import (
    InvalidSignatureException,
    InvalidAppIdException,
)
from utils import get_hs_stock


TOKEN = os.getenv('WECHAT_TOKEN', 'stockquery')
AES_KEY = os.getenv('WECHAT_AES_KEY', '')
APPID = os.getenv('WECHAT_APPID', '')


app = Flask(__name__)
app.config.from_object(__name__) # load config from this file , flaskr.py

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE = os.path.join(app.root_path, 'stockquery.db'),
    SECRET_KEY = '400c7f3461f843c0b07a9e5285f92ed6',
))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)


def connect_db():
    """Connects to the specific database."""
    urllib.parse.uses_netloc.append("postgres")
    url = urllib.parse.urlparse(os.environ.get("DATABASE_URL"))

    if os.environ.get("DATABASE_URL"):
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
    else:
        conn = psycopg2.connect(
            dbname='stockquery',
            user='postgres',
            password='123456',
            host='127.0.0.1',
            port='5432'
        )
    return conn

# print(connect_db())


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'pg_db'):
        g.pg_db = connect_db()
    return g.pg_db


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'pg_db'):
        g.pg_db.close()


def init_db():
    db = get_db()
    cur = db.cursor()
    with app.open_resource('schema.sql', mode='r') as f:
        for sql in f.read().split(';'):
            if sql.strip():
                cur.execute(sql.strip())
    db.commit()


@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Initialized the database.')


def encode_password(password):
    return hashlib.md5(('slat:stockquery' + password).encode()).hexdigest()


def create_user(username, password):
    """ 创建用户 """
    # 对密码进行加密
    raw_password = encode_password(password)
    # SQL 语句创建用户
    sql_script = """INSERT INTO "user" (username, password)
                    VALUES ('{}', '{}')
                 """.format(username, raw_password)
    db = get_db()
    cur = db.cursor()
    cur.execute(sql_script)
    db.commit()


@app.cli.command('initadmin')
def initadmin_command():
    """Initializes the admin."""
    create_user('admin', '123456')
    print('Initialized the admin.')


def query_user(username):
    """ 查询用户 """
    db = get_db()
    sql_script = """SELECT * FROM "user" WHERE username='{}'
                 """.format(username)
    cur = db.cursor()
    cur.execute(sql_script)
    user = cur.fetchone()
    return user


@app.cli.command('queryadmin')
def queryadmin_command():
    """query the admin."""
    print(query_user('admin'))


def add_history(user_id, stock_code, result):
    db = get_db()
    now = datetime.datetime.now()
    sql_script = """INSERT INTO history (user_id, stock_code, result, query_time)
                    VALUES ('{}', '{}', '{}', '{}')
                 """.format(user_id, stock_code, result, now)
    cur = db.cursor()
    cur.execute(sql_script)
    db.commit()


def query_all_history(user_id):
    db = get_db()
    sql_script = """SELECT * FROM history
                    WHERE user_id={} ORDER BY query_time DESC
                 """.format(user_id)
    cur = db.cursor()
    cur.execute(sql_script)
    histories = cur.fetchall()
    return histories


def add_wxuser_history(openid, stock_code, result):
    db = get_db()
    now = datetime.datetime.now()
    sql_script = """INSERT INTO wxuser_history (openid, stock_code, result, query_time)
                    VALUES ('{}', '{}', '{}', '{}')
                 """.format(openid, stock_code, result, now)
    cur = db.cursor()
    cur.execute(sql_script)
    db.commit()


def query_all_wxuser_history(openid):
    db = get_db()
    sql_script = """SELECT openid, stock_code, result, query_time FROM wxuser_history
                    WHERE openid='{}' ORDER BY query_time DESC
                 """.format(openid)
    cur = db.cursor()
    cur.execute(sql_script)
    histories = cur.fetchall()
    return histories


@app.route('/register/', methods=['GET', 'POST'])
def register():
    """ 用户注册功能 """
    context = {}
    if request.method == 'POST':
        # print(request.form)
        username = request.form.get('username')
        password = request.form.get('password')
        re_password = request.form.get('re_password')
        error = None
        if not username:
            error = '用户名不能为空'
        elif not (password and re_password):
            error = '请输入密码和确认密码'
        elif password != re_password:
            error = '两次密码输入不一致'
        elif query_user(username):
            error = '用户已存在'

        if error is None:
            create_user(username, password)
            return redirect(url_for('login'))
        else:
            context.update({
                'error': error,
                'username': username
            })
    return render_template('register.html', **context)


@app.route('/login/', methods=['GET', 'POST'])
def login():
    context = {}
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        error = None

        if not username:
            error = '请输入用户名'
        else:
            user = query_user(username)
            if not user:
                error = '用户不存在'
            else:
                user_password = user[2]
                if user_password != encode_password(password):
                    error = '登录密码不正确，请确认密码或者用户名'
                else:
                    session['login'] = True
                    session['user'] = user
                    return redirect(url_for('query'))

        context.update({
            'error': error,
            'username': username
        })
    return render_template('login.html', **context)


@app.route('/logout/')
def logout():
    session['login'] = False
    session['user'] = None
    return redirect(url_for('query'))


@app.route('/')
def query():
    context = {}
    stock_code = request.args.get('stock_code', '')
    if stock_code:
        query_result = get_hs_stock(stock_code)
        user = session.get('user')
        if user:
            add_history(user[0], stock_code, query_result)
        context.update({
            'stock_code': stock_code,
            'query_result': query_result,
        })
    return render_template('index.html', **context)
    # **context 相当于 stock_code=stock_code, query_result=query_result

@app.route('/history/')
def history():
    user = session.get('user')
    if user:
        context = {
            'history': query_all_history(user[0])
        }
    else:
        context = {'history': ''}
    return render_template('index.html', **context)

@app.route('/help/')
def help():
    help_str = """
        <p>1. 查询沪深股市股票价格，sh 开头表示沪股，sz 开头表示深股 </p>
        <p>2. 点击查询历史，查看历史查询记录 </p>
        <p>3. 点击查询帮助，查看帮助文档 </p>
    """
    return render_template('index.html', help=help_str)


@app.route('/wx/', methods=['GET', 'POST'])
def wechat():
    signature = request.args.get('signature', '')
    timestamp = request.args.get('timestamp', '')
    nonce = request.args.get('nonce', '')
    encrypt_type = request.args.get('encrypt_type', 'raw')
    msg_signature = request.args.get('msg_signature', '')
    try:
        check_signature(TOKEN, signature, timestamp, nonce)
    except InvalidSignatureException:
        abort(403)
    if request.method == 'GET':
        echo_str = request.args.get('echostr', '')
        return echo_str

    _help = """1. 查询沪深股市股票价格，sh 开头表示沪股，sz 开头表示深股\n2. 输入'历史'，查看历史查询记录\n3. 输入：'帮助'，查看帮助文档\n"""

    # plaintext mode
    msg = parse_message(request.data)
    if msg.type == 'text':
        # 微信用户的 openid
        openid = msg.source
        # 历史
        if msg.content in ['历史']:
            histories = query_all_wxuser_history(openid)
            histories_str = "".join([
                '{} 查询 {}: {}\n'.format(item[3], item[1], item[2])
                for item in histories
            ])
            if histories_str:
                reply = create_reply(histories_str, msg)
            else:
                reply = create_reply('未有查询记录', msg)
        # 帮助
        elif msg.content in ['帮助']:
            reply = create_reply(_help, msg)
        # 股价查询
        else:
            result = get_hs_stock(msg.content)
            add_wxuser_history(openid, msg.content, result)
            reply = create_reply(result, msg)
    else:
        reply = create_reply('对不起，无法识别!!', msg)
    return reply.render()
