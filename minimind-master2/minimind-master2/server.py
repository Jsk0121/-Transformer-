from flask import Flask, request, jsonify, session, render_template, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import torch
from transformers import AutoTokenizer
from model.model import MiniMindLM
from model.LMConfig import LMConfig
import argparse
import random
import datetime

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    chats = db.relationship('Chat', backref='user', lazy=True)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    messages = db.relationship('Message', backref='chat', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Model initialization
def init_model(args):
    tokenizer = AutoTokenizer.from_pretrained('./model/minimind_tokenizer')
    model = MiniMindLM(LMConfig(
        dim=args.dim,
        n_layers=args.n_layers,
        max_seq_len=args.max_seq_len,
        use_moe=args.use_moe
    ))
    
    ckp = f'./{args.out_dir}/full_sft_{args.dim}.pth'
    state_dict = torch.load(ckp, map_location=args.device)
    model.load_state_dict({k: v for k, v in state_dict.items() if 'mask' not in k}, strict=True)
    
    return model.eval().to(args.device), tokenizer

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--dim', default=512, type=int)
parser.add_argument('--n_layers', default=8, type=int)
parser.add_argument('--max_seq_len', default=512, type=int)
parser.add_argument('--use_moe', default=False, type=bool)
parser.add_argument('--out_dir', default='out', type=str)
parser.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu', type=str)
parser.add_argument('--temperature', default=0.85, type=float)
parser.add_argument('--top_p', default=0.85, type=float)
args = parser.parse_args()

# Initialize model and tokenizer
model, tokenizer = init_model(args)

# Authentication routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
        
    user = User(
        username=username,
        password_hash=generate_password_hash(password)
    )
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'Registration successful'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        return jsonify({'message': 'Login successful'}), 200
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logout successful'}), 200

# Chat routes
@app.route('/api/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    data = request.get_json()
    messages = data.get('messages', [])
    chat_id = data.get('chat_id')
    
    # Create new chat if chat_id not provided
    if not chat_id:
        new_chat = Chat(user_id=session['user_id'], title=messages[0]['content'][:50])
        db.session.add(new_chat)
        db.session.commit()
        chat_id = new_chat.id

    # Generate response using the model
    with torch.no_grad():
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )[-args.max_seq_len + 1:]

        x = torch.tensor(tokenizer(prompt)['input_ids'], device=args.device).unsqueeze(0)
        outputs = model.generate(
            x,
            eos_token_id=tokenizer.eos_token_id,
            max_new_tokens=args.max_seq_len,
            temperature=args.temperature,
            top_p=args.top_p,
            pad_token_id=tokenizer.pad_token_id
        )
        
        response = tokenizer.decode(outputs.squeeze()[x.shape[1]:].tolist(), skip_special_tokens=True)

    # Save messages to database
    for msg in messages:
        message = Message(chat_id=chat_id, role=msg['role'], content=msg['content'])
        db.session.add(message)
    
    # Save model response
    message = Message(chat_id=chat_id, role='assistant', content=response)
    db.session.add(message)
    db.session.commit()

    return jsonify({
        'response': response,
        'chat_id': chat_id
    })

@app.route('/api/chats', methods=['GET'])
def get_chats():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    user_chats = Chat.query.filter_by(user_id=session['user_id']).order_by(Chat.created_at.desc()).all()
    chats = []
    for chat in user_chats:
        messages = Message.query.filter_by(chat_id=chat.id).order_by(Message.created_at).all()
        chats.append({
            'id': chat.id,
            'title': chat.title,
            'messages': [{
                'role': msg.role,
                'content': msg.content
            } for msg in messages]
        })
    
    return jsonify(chats)

# Serve index.html
@app.route('/')
def index():
    return render_template('index.html')

# Serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000) 