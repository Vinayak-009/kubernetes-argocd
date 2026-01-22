import os
import enum
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum as SQLAlchemyEnum

app = Flask(__name__)

# --- Configuration ---
# Use Env vars provided by K8s, fallback to local for testing
user = os.getenv('DB_USERNAME', 'postgres')
pwd = os.getenv('DB_PASSWORD', 'password')
host = os.getenv('DB_HOST', 'localhost')
port = os.getenv('DB_PORT', '5432')
db_name = os.getenv('DB_NAME', 'employees_db')

app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'super-secret-key-for-ui-flashing'

db = SQLAlchemy(app)

# --- Models & Enums ---
class Department(enum.Enum):
    HR = "Human Resources"
    ENGINEERING = "Engineering"
    SALES = "Sales"
    MARKETING = "Marketing"
    FINANCE = "Finance"
    IT = "IT Support"

class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    department = db.Column(SQLAlchemyEnum(Department), nullable=False)
    salary = db.Column(db.Float, nullable=False)
    hire_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': f"{self.first_name} {self.last_name}",
            'email': self.email,
            'department': self.department.value,
            'salary': self.salary,
            'hire_date': self.hire_date.isoformat()
        }

# --- Routes ---

@app.route('/health')
def health():
    """K8s Liveness/Readiness Probe Endpoint"""
    try:
        # Check DB connection
        db.session.execute(db.text('SELECT 1'))
        return jsonify({"status": "healthy", "db": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/')
def index():
    # Basic search functionality
    query = request.args.get('q')
    if query:
        # Search by ID or Email
        if query.isdigit():
            employees = Employee.query.filter_by(id=int(query)).all()
        else:
            employees = Employee.query.filter(Employee.email.ilike(f"%{query}%")).all()
    else:
        employees = Employee.query.order_by(Employee.id.desc()).all()
        
    return render_template('index.html', employees=employees)

@app.route('/hire', methods=['GET', 'POST'])
def hire():
    if request.method == 'POST':
        try:
            new_emp = Employee(
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                email=request.form['email'],
                department=Department[request.form['department']], # Convert string to Enum
                salary=float(request.form['salary']),
                hire_date=datetime.strptime(request.form['hire_date'], '%Y-%m-%d')
            )
            db.session.add(new_emp)
            db.session.commit()
            flash('Employee hired successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error hiring employee: {str(e)}', 'error')

    return render_template('form.html', action="Hire", employee=None, departments=Department)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    employee = Employee.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            employee.first_name = request.form['first_name']
            employee.last_name = request.form['last_name']
            employee.email = request.form['email']
            employee.department = Department[request.form['department']]
            employee.salary = float(request.form['salary'])
            # Don't change hire date usually, but allow if needed
            employee.hire_date = datetime.strptime(request.form['hire_date'], '%Y-%m-%d')
            
            db.session.commit()
            flash('Employee details updated!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error updating: {str(e)}', 'error')

    return render_template('form.html', action="Update", employee=employee, departments=Department)

@app.route('/fire/<int:id>', methods=['POST'])
def fire(id):
    employee = Employee.query.get_or_404(id)
    try:
        db.session.delete(employee)
        db.session.commit()
        flash('Employee record removed.', 'warning')
    except Exception as e:
        flash(f'Error deleting: {str(e)}', 'error')
    return redirect(url_for('index'))

# Create DB Tables if they don't exist
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)