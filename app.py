import os
from flask import render_template
from flask import Flask, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename



app = Flask(__name__)

UPLOAD_FOLDER = os.path.join("static", "uploads")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql+psycopg2://admin:secret@localhost:5432/ecommerce')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'some_super_secret_string')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    password_hash = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    role = db.Column(db.String, nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    __tablename__ = "product"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Cart(db.Model):
    __tablename__ = "cart"
    id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    productid = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product')

class OrderHistory(db.Model):
    __tablename__ = "orderhistory"
    id = db.Column(db.Integer, primary_key=True)
    productid = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product = db.relationship('Product')

class Transaction(db.Model):
    __tablename__ = "transaction"
    id = db.Column(db.Integer, primary_key=True)
    order_history_id = db.Column(db.Integer, db.ForeignKey('orderhistory.id'), nullable=False)
   


@app.route('/')
def home():
    all_products = Product.query.all()
    return render_template('home.html', all_products=all_products)

@app.route('/auth/register', methods=['POST', 'GET'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    data = request.form
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    hashed_password = generate_password_hash(password)

    user_role = 'admin' if email == 'admins@example.com' else 'user'

    new_user = User(name=name, email=email, password_hash=hashed_password, role=user_role)

    db.session.add(new_user)
    db.session.commit()

    return redirect(url_for('login'))

@app.route('/auth/login', methods=['POST', 'GET'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    data = request.form
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return {"message": "Invalid credentials!"}, 401

    session['user_id'] = user.id
    session['role'] = user.role
    session['user_name'] = user.name

    return redirect(url_for('home'))


@app.route('/products', methods=['POST','GET'])
def add_product():
    if 'user_id' not in session:
        return {"error": "You must be logged in!"}, 401
    
    if request.method == 'GET':
        return render_template('add_product.html')
    
    if session.get('role') != 'admin':
        return {"error": "Admins only!"}, 403

    data = request.form
    name = data.get('name')
    description = data.get('description')
    price = data.get('price')
    stock = data.get('stock')
    # image_url = f"/static/uploads/{filename}"

    if 'image_file' not in request.files:
        return {"error": "No image file provided!"}, 400
    
    file = request.files['image_file']
    if file.filename == '':
        return {"error": "No image file provided!"}, 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_url = f"/static/uploads/{filename}"
    else:
        return {"error": "Invalid file type!"}, 400

    new_product = Product(name=name, description=description, price=price, stock=stock, image_url=image_url)
    db.session.add(new_product)
    db.session.commit()
    return render_template('add_product.html', message="Product added successfully!")

@app.route('/product_list', methods=['GET'])
def get_products():
    products = Product.query.all()
    return {"products": [{"id": product.id, "name": product.name, "description": product.description, "price": product.price, "stock": product.stock, "image_url": product.image_url} for product in products]}, 200

@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return "Product not found!", 404
    return render_template('product_detail.html', product=product)

@app.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    if 'user_id' not in session:
        return {"error": "You must be logged in!"}, 401
    if session.get('role') != 'admin':
        return {"error": "Admins only!"}, 403

    product = Product.query.get(product_id)
    if not product:
        return {"error": "Product not found!"}, 404
    db.session.delete(product)
    db.session.commit()
    return {"message": "Product deleted successfully!"}, 200

@app.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    if 'user_id' not in session:
        return {"error": "You must be logged in!"}, 401
    if session.get('role') != 'admin':
        return {"error": "Admins only!"}, 403

    product = Product.query.get(product_id)
    if not product:
        return {"error": "Product not found!"}, 404
    
    data = request.form
    name = data.get('name')
    description = data.get('description')
    price = data.get('price')
    stock = data.get('stock')
    image_url = data.get('image_url')

    product.name = data.get('name', product.name)
    product.description = data.get('description', product.description)
    product.price = data.get('price', product.price)
    product.stock = data.get('stock', product.stock)
    product.image_url = data.get('image_url', product.image_url)

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cart = Cart.query.filter_by(userid=session['user_id']).all()
    return render_template('cart.html', cart=cart)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    quantity = int(request.form.get('quantity', 1)) 
    
    existing_item = Cart.query.filter_by(userid=user_id, productid=product_id).first()
    
    if existing_item:
        existing_item.quantity += quantity
    else:
        product = Product.query.get(product_id)
        new_item = Cart(userid=user_id, productid=product_id, quantity=quantity, price=product.price)
        db.session.add(new_item)
        
    db.session.commit()
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    user_cart = Cart.query.filter_by(userid=user_id).all()
    
    if not user_cart:
        return "Your cart is empty!", 400
        
    for item in user_cart:
        
        product = Product.query.get(item.productid)
        if product.stock >= item.quantity:
            product.stock -= item.quantity
            
        total_price = item.quantity * item.price
        new_order = OrderHistory(
            userid=user_id,
            productid=item.productid,
            quantity=item.quantity,
            total_price=total_price
        )
        db.session.add(new_order)
        db.session.delete(item)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_orders = OrderHistory.query.filter_by(userid=session['user_id']).order_by(OrderHistory.created_at.desc()).all()
    return render_template('orders.html', orders=user_orders)


@app.route('/auth/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)



