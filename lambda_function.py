from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
# from config import username, password, endpoint
from datetime import datetime
from functools import wraps
from flask import request, jsonify
import awsgi
import os


app = Flask(__name__)
CORS(app)

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

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # user = db.relationship('Users', backref='likes')
    # post = db.relationship('Post', backref='likes')
    # comment = db.relationship('Comment', backref='likes')



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
    posts_data = []
    
    for post in posts:
        # Count the likes for each post
        likes_count = Like.query.filter_by(post_id=post.id).count()
        
        posts_data.append({
            'id': post.id,
            'author': post.author,
            'content': post.content,
            'likes': likes_count,  # Use the count of likes from the likes table
            'created_at': post.created_at.isoformat()
        })

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
    likes_count = Like.query.filter_by(post_id=post.id).count()  # Count likes for this post

    post_data = {
        'id': post.id,
        'author': post.author,
        'content': post.content,
        'likes': likes_count,  # Use the likes count from the likes table
        'created_at': post.created_at.isoformat()
    }
    return jsonify(post_data), 200


#TODO: Implement this endpoint later and add to gateway if needed. 
@app.route('/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    data = request.json
    post.likes = data.get('likes', post.likes)
    # Update other fields as needed
    # Implement later, we don't need this endpoint rn
    db.session.commit()
    return jsonify({"message": "Post modified!"}), 200


@app.route('/posts/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    # Placeholder for actual user ID retrieval logic
    current_user_id = request.json.get('user_id')
    post = Post.query.get_or_404(post_id)
    
    # Check if the like already exists
    existing_like = Like.query.filter_by(user_id=current_user_id, post_id=post_id).first()
    
    if existing_like:
        # If like exists, remove it (unlike)
        db.session.delete(existing_like)
        post.likes = max(post.likes - 1, 0)
        action = 'unliked'
    else:
        # If like does not exist, add a new like
        new_like = Like(user_id=current_user_id, post_id=post_id)
        db.session.add(new_like)
        post.likes += 1
        action = 'liked'
    
    # Commit changes to the database
    db.session.commit()
    
    # Return the current like count for the post
    like_count = Like.query.filter_by(post_id=post_id).count()
    return jsonify({'status': action, 'likes': like_count}), 200


@app.route('/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    # First delete all comments associated with the post
    Comment.query.filter_by(post_id=post_id).delete()

    # Then delete the post
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Post deleted'}), 200

# --------------------------------------- COMMENTS ---------------------------------------
@app.route('/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    comments = Comment.query.filter_by(post_id=post_id).all()
    comments_data = []
    for comment in comments:
        # Count the likes for each comment
        likes_count = Like.query.filter_by(comment_id=comment.id).count()
        comments_data.append({
            'id': comment.id,
            'author': comment.author,
            'content': comment.content,
            'likes': likes_count,  # Replace comment.likes with the count from likes table
            'created_at': comment.created_at.isoformat()
        })
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
    user_id = request.json.get('user_id')  # Assuming you pass the user ID in the request
    like = Like.query.filter_by(comment_id=comment_id, user_id=user_id).first()
    comment = Comment.query.get_or_404(comment_id)

    if request.json.get('like'):
        # If the user wants to like but the like doesn't exist, create it
        if not like:
            new_like = Like(user_id=user_id, comment_id=comment_id)
            db.session.add(new_like)
            comment.likes += 1
            message = 'Like added.'
        else:
            message = 'Like already exists.'
    else:
        # If the user wants to remove the like and it exists, delete it
        if like:
            db.session.delete(like)
            comment.likes = max(comment.likes - 1, 0)
            message = 'Like removed.'
        else:
            message = 'Like does not exist.'

    db.session.commit()
    likes_count = Like.query.filter_by(comment_id=comment_id).count()  # Count current likes for the comment
    return jsonify({'message': message, 'likes': likes_count}), 200

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

    origin = headers.get('origin') if headers else 'https://purepoker.world'

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