import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'minimind-master2'))

from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import datetime
import sqlite3
import argparse
import torch
from transformers import AutoTokenizer
from model.model import MiniMindLM
from model.LMConfig import LMConfig
from functools import wraps

app = Flask(__name__)
CORS(app)  # 启用CORS以允许前端访问

# JWT配置
SECRET_KEY = 'your-secret-key'  # 在生产环境中应该使用更安全的密钥
JWT_EXPIRATION = datetime.timedelta(days=1)

# 数据库初始化
def init_db():
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    # 创建用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    # 创建对话历史表
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  title TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    # 创建消息表
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  conversation_id INTEGER,
                  role TEXT,
                  content TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (conversation_id) REFERENCES conversations (id))''')
    conn.commit()
    conn.close()

# 初始化模型
def init_model():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"使用设备: {device}")
    
    # 获取项目根目录的绝对路径
    base_path = os.path.dirname(os.path.abspath(__file__))
    model_base_path = os.path.join(base_path, 'minimind-master2')
    
    # 初始化模型配置
    config = LMConfig(
        dim=512,
        n_layers=8,
        max_seq_len=512,
        use_moe=False
    )
    
    # 创建模型实例
    model = MiniMindLM(config)
    
    # 加载模型权重
    model_path = os.path.join(model_base_path, 'out', 'full_sft_512.pth')
    print(f"加载模型权重: {model_path}")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}\n当前目录: {os.getcwd()}")
        
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict({k: v for k, v in state_dict.items() if 'mask' not in k}, strict=True)
    
    # 加载分词器
    tokenizer_path = os.path.join(model_base_path, 'model', 'minimind_tokenizer')
    print(f"加载分词器: {tokenizer_path}")
    
    if not os.path.exists(tokenizer_path):
        raise FileNotFoundError(f"分词器目录不存在: {tokenizer_path}")
        
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
    
    return model.eval().to(device), tokenizer

# 用户认证装饰器
def require_auth(f):
    @wraps(f)
    def auth_wrapper(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'message': '缺少认证令牌'}), 401
        
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user = data['user_id']
        except:
            return jsonify({'message': '无效的认证令牌'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return auth_wrapper

# 路由
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')  # 实际应用中应该哈希处理密码
    
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, password))
        conn.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '邮箱已被注册'})
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    c.execute('SELECT id, password FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    conn.close()
    
    if user and user[1] == password:  # 实际应用中应该验证哈希密码
        token = jwt.encode({
            'user_id': user[0],
            'exp': datetime.datetime.utcnow() + JWT_EXPIRATION
        }, SECRET_KEY, algorithm='HS256')
        return jsonify({'token': token})
    
    return jsonify({'message': '邮箱或密码错误'}), 401

@app.route('/api/chat', methods=['POST'])
@require_auth
def chat(current_user):
    data = request.get_json()
    message = data.get('message')
    conversation_id = data.get('conversation_id')
    
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    
    # 如果没有conversation_id，创建新对话
    if not conversation_id:
        c.execute('INSERT INTO conversations (user_id, title) VALUES (?, ?)',
                 (current_user, message[:20] + '...'))
        conversation_id = c.lastrowid
    
    # 保存用户消息
    c.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
             (conversation_id, 'user', message))
    
    try:
        # 获取模型回复
        with torch.no_grad():
            input_ids = tokenizer.encode(tokenizer.bos_token + message, return_tensors='pt').to(model.device)
            outputs = model.generate(
                input_ids,
                max_new_tokens=512,
                temperature=0.85,
                top_p=0.85,
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id
            )
            reply = tokenizer.decode(outputs.squeeze()[input_ids.shape[1]:], skip_special_tokens=True)
        
        # 保存模型回复
        c.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                 (conversation_id, 'assistant', reply))
        
        conn.commit()
        
        return jsonify({
            'reply': reply,
            'conversation_id': conversation_id
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/history', methods=['GET'])
@require_auth
def get_chat_history(current_user):
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    c.execute('''SELECT id, title, created_at 
                 FROM conversations 
                 WHERE user_id = ? 
                 ORDER BY created_at DESC''', (current_user,))
    conversations = [{'id': row[0], 'title': row[1], 'created_at': row[2]} 
                    for row in c.fetchall()]
    conn.close()
    return jsonify(conversations)

if __name__ == '__main__':
    # 初始化数据库
    init_db()
    
    # 初始化模型
    print("正在加载模型...")
    model, tokenizer = init_model()
    print("模型加载完成！")
    
    # 启动服务器
    app.run(port=5000, debug=True) 