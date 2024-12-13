from flask import Flask, request, render_template, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from azure.storage.blob import BlobServiceClient
import os

# Initialize Flask app and configurations
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurants.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize database and migration
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Azure Blob Storage Configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)

# Database Models
class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    image = db.Column(db.String(200), nullable=True)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(300), nullable=True)

# Utility function to get average star rating
@app.context_processor
def utility_processor():
    def star_rating(reviews):
        if not reviews:
            return "No ratings yet"
        total = sum([r.rating for r in reviews])
        return round(total / len(reviews), 1)
    return dict(star_rating=star_rating)

# Routes
@app.route('/')
def index():
    restaurants = Restaurant.query.all()
    return render_template('index.html', restaurants=restaurants)

@app.route('/details/<int:id>')
def details(id):
    restaurant = Restaurant.query.get_or_404(id)
    reviews = Review.query.filter_by(restaurant_id=id).all()
    return render_template('details.html', restaurant=restaurant, reviews=reviews)

@app.route('/create_restaurant')
def create_restaurant():
    return render_template('create_restaurant.html')

@app.route('/add_restaurant', methods=['POST'])
def add_restaurant():
    name = request.form['name']
    description = request.form['description']
    image = request.files['image']

    # Upload image to Azure Blob Storage
    if image:
        blob_client = container_client.get_blob_client(image.filename)
        blob_client.upload_blob(image, overwrite=True)
        image_url = f"https://{container_client.account_name}.blob.core.windows.net/{AZURE_STORAGE_CONTAINER_NAME}/{image.filename}"
    else:
        image_url = None

    restaurant = Restaurant(name=name, description=description, image=image_url)
    db.session.add(restaurant)
    db.session.commit()
    flash('Restaurant added successfully!')
    return redirect(url_for('index'))

@app.route('/add_review/<int:id>', methods=['POST'])
def add_review(id):
    restaurant = Restaurant.query.get_or_404(id)
    rating = int(request.form['rating'])
    comment = request.form['comment']

    review = Review(restaurant_id=restaurant.id, rating=rating, comment=comment)
    db.session.add(review)
    db.session.commit()
    flash('Review added successfully!')
    return redirect(url_for('details', id=restaurant.id))

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    if file:
        blob_client = container_client.get_blob_client(file.filename)
        blob_client.upload_blob(file, overwrite=True)
        return f"File '{file.filename}' uploaded successfully!"
    return "No file selected", 400

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        blob_client = container_client.get_blob_client(filename)
        blob_data = blob_client.download_blob()
        return send_file(
            blob_data.readall(),
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return f"Error downloading the file: {str(e)}", 404

@app.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='favicon.ico'))

# Run the application
if __name__ == '__main__':
    app.run(debug=True)
