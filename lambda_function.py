from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
# from config import username, password, endpoint
from datetime import datetime
from functools import wraps
from flask import request, jsonify
import awsgi
import os
import requests


app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
username = os.getenv('username')
password = os.getenv('password')
endpoint = os.getenv('endpoint')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{username}:{password}@{endpoint}/pure_poker'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    likes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    likes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Wrap db.create_all in an application context
with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_cookie = request.cookies.get('pure-poker-token')
        if auth_cookie:
            # Send a request to the authentication service for validation
            validation_response = requests.post('http://authentication_service_endpoint/validate_token', 
                                                cookies={'pure-poker-token': auth_cookie})
            if validation_response.status_code == 200:
                return f(*args, **kwargs)
        return jsonify({'message': 'Unauthorized'}), 401
    return decorated_function



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
    # First delete all comments associated with the post
    Comment.query.filter_by(post_id=post_id).delete()

    # Then delete the post
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Post deleted'}), 200

# COMMENTS
@app.route('/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    comments = Comment.query.filter_by(post_id=post_id).all()
    comments_data = [{
        'id': comment.id,
        'author': comment.author,
        'content': comment.content,
        'likes': comment.likes,
        'created_at': comment.created_at.isoformat()
    } for comment in comments]
    return jsonify(comments_data), 200

@app.route('/posts/<int:post_id>/comments', methods=['POST'])
def create_comment(post_id):
    data = request.json
    new_comment = Comment(post_id=post_id, author=data['author'], content=data['content'])
    db.session.add(new_comment)
    db.session.commit()
    return jsonify({
        'id': new_comment.id, 
        'author': new_comment.author,
        'content': new_comment.content,
        'likes': new_comment.likes,
        'created_at': new_comment.created_at.isoformat()
    }), 201


@app.route('/comments/<int:comment_id>/like', methods=['POST'])
def like_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    data = request.json
    if data.get('like'):
        comment.likes += 1
    else:
        comment.likes = max(comment.likes - 1, 0)
    db.session.commit()
    return jsonify({'likes': comment.likes}), 200

@app.route('/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'message': 'Comment deleted'}), 200



# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0', port=8012, use_reloader=False)


def lambda_handler(event, context):
    print("Here we go!")
    response = awsgi.response(app, event, context)

    # Check if the headers exist in the event and set the origin accordingly
    headers = event.get('headers', {})
    # origin = headers.get('origin') if headers else 'https://www.unilate.be'
    origin = headers.get('origin')

    # Prepare the response headers
    response_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,PUT,POST,DELETE,OPTIONS"
    }

    # Construct the modified response
    modified_response = {
        "isBase64Encoded": False,
        "statusCode": response['statusCode'],
        "headers": response_headers,
        "multiValueHeaders": response.get('multiValueHeaders', {}),
        "body": response['body']
    }

    # Check if 'Set-Cookie' is in the Flask response headers and add it to the multiValueHeaders
    flask_response_headers = response.get('headers', {})
    if 'Set-Cookie' in flask_response_headers:
        # AWS API Gateway expects the 'Set-Cookie' header to be in multiValueHeaders
        modified_response['multiValueHeaders']['Set-Cookie'] = [flask_response_headers['Set-Cookie']]

    return modified_response