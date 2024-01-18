from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from config import username, password, endpoint
from datetime import datetime




app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{username}:{password}@{endpoint}/pure_poker'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    likes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Wrap db.create_all in an application context
with app.app_context():
    db.create_all()


# Health Check endpoint
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/posts', methods=['GET'])
def get_posts():
    posts = Post.query.all()
    posts_data = [{
        'id': post.id,
        'author': post.author,
        'content': post.content,
        'likes': post.likes,
        'created_at': post.created_at.isoformat()
    } for post in posts]
    return jsonify(posts_data), 200

@app.route('/posts', methods=['POST'])
def create_post():
    data = request.json
    new_post = Post(author=data['author'], content=data['content'])
    db.session.add(new_post)
    db.session.commit()
    return jsonify({'message': 'Post added successfully'}), 201

@app.route('/posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    post = Post.query.get_or_404(post_id)
    post_data = {
        'id': post.id,
        'author': post.author,
        'content': post.content,
        'likes': post.likes,
        'created_at': post.created_at.isoformat() 
    }
    return jsonify(post_data), 200

@app.route('/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    data = request.json
    post.likes = data.get('likes', post.likes)
    # Update other fields as needed
    db.session.commit()
    return jsonify({"message": "Post modified!"}), 200


@app.route('/posts/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    data = request.json
    if data.get('like'):
        post.likes += 1  # Increment the likes
    else:
        post.likes = max(post.likes - 1, 0)  # Decrement the likes, but don't go below 0
    db.session.commit()
    return jsonify({'likes': post.likes}), 200



@app.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Post deleted'}), 200





if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8012, use_reloader=False)

