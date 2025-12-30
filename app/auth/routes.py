"""
Authentication routes and business logic
"""
import re
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.models import User
from app import db


def validate_password_complexity(password):
    """
    Password complexity validation (strict enforcement of design document requirements)
    Requirements:
    1. Length > 6 bytes
    2. Must contain at least two of: uppercase letters, lowercase letters, digits, special characters
    
    :param password: Password to validate
    :return: (bool, str) - (passed or not, error message)
    """
    # Check length
    if len(password) <= 6:
        return False, "密码长度必须大于 6 个字符"
    
    # Define regex patterns for character types
    has_uppercase = bool(re.search(r'[A-Z]', password))  # Uppercase letters
    has_lowercase = bool(re.search(r'[a-z]', password))  # Lowercase letters
    has_digit = bool(re.search(r'[0-9]', password))      # Digits
    has_special = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password))  # Special characters
    
    # Count number of character types satisfied
    type_count = sum([has_uppercase, has_lowercase, has_digit, has_special])
    
    if type_count < 2:
        return False, "密码必须包含大写字母、小写字母、数字、特殊字符中的至少两种"
    
    return True, ""


def validate_email_format(email):
    """
    Email format validation
    :param email: Email to validate
    :return: bool - Whether valid
    """
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    # Redirect to home page if already authenticated
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Form data validation
        if not username or not email or not password:
            flash('所有字段均为必填项！', 'danger')
            return render_template('auth/register.html')
        
        # Validate username length
        if len(username) > 50:
            flash('用户名长度不能超过 50 个字符！', 'danger')
            return render_template('auth/register.html')
        
        # Validate email format
        if not validate_email_format(email):
            flash('邮箱格式不正确！', 'danger')
            return render_template('auth/register.html')
        
        # Validate email length
        if len(email) > 100:
            flash('邮箱长度不能超过 100 个字符！', 'danger')
            return render_template('auth/register.html')
        
        # Validate password complexity (core design document requirement)
        is_valid, error_msg = validate_password_complexity(password)
        if not is_valid:
            flash(error_msg, 'danger')
            return render_template('auth/register.html')
        
        # Verify passwords match
        if password != confirm_password:
            flash('两次输入的密码不一致！', 'danger')
            return render_template('auth/register.html')
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('该用户名已被注册！', 'danger')
            return render_template('auth/register.html')
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('该邮箱已被注册！', 'danger')
            return render_template('auth/register.html')
        
        # Create new user
        try:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            flash('注册成功！请登录。', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'注册失败：{str(e)}', 'danger')
            return render_template('auth/register.html')
    
    # GET request, render registration page
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    # Redirect to home page if already authenticated
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        # Form data validation
        if not username or not password:
            flash('用户名和密码不能为空！', 'danger')
            return render_template('auth/login.html')
        
        # Find user (supports both username and email login)
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        # Verify user and password
        if user is None or not user.check_password(password):
            flash('用户名或密码错误！', 'danger')
            return render_template('auth/login.html')
        
        # Login user
        login_user(user, remember=bool(remember))
        flash(f'欢迎回来，{user.username}！', 'success')
        
        # Redirect to next page specified in 'next' parameter, or home page
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('index'))
    
    # GET request, render login page
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    username = current_user.username
    logout_user()
    flash(f'再见，{username}！', 'info')
    return redirect(url_for('index'))
