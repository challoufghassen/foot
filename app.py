from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, timedelta
import uuid
import hashlib
from werkzeug.utils import secure_filename
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Database configuration
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'football_manager'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432')
}

# File upload configuration
UPLOAD_FOLDER = 'uploads/photos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_filename(filename):
    """Generate a unique filename to prevent collisions"""
    ext = filename.rsplit('.', 1)[1].lower()
    unique_id = str(uuid.uuid4())
    return f"{unique_id}.{ext}"

@app.route('/api/register', methods=['POST'])
def register_player():
    try:
        # Get form data
        data = request.form
        photo = request.files.get('photo')
        
        if not photo or not allowed_file(photo.filename):
            return jsonify({'error': 'Invalid photo file'}), 400
            
        # Generate unique filename and save photo
        filename = generate_unique_filename(photo.filename)
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        photo.save(photo_path)
        
        # Get consent data
        consent_data = json.loads(data.get('consent_data', '{}'))
        
        # Connect to database
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Start transaction
            cur.execute("BEGIN")
            
            # Insert player data
            cur.execute("""
                INSERT INTO players (player_id, full_name, team, position, access_level, photo_path)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                data['player_id'],
                data['full_name'],
                data['team'],
                data.get('position'),
                data['access_level'],
                photo_path
            ))
            
            player_id = cur.fetchone()['id']
            
            # Record consent
            cur.execute("""
                INSERT INTO consent_records 
                (player_id, consent_type, consent_given, consent_version, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                player_id,
                'photo_usage',
                consent_data.get('photo_consent', False),
                '1.0',
                request.remote_addr,
                request.user_agent.string
            ))
            
            # Set data retention period (e.g., 2 years)
            retention_period = 730  # 2 years in days
            cur.execute("""
                INSERT INTO data_retention 
                (player_id, retention_period, retention_reason, expires_at)
                VALUES (%s, %s, %s, %s)
            """, (
                player_id,
                retention_period,
                'Active player registration',
                datetime.now() + timedelta(days=retention_period)
            ))
            
            # Commit transaction
            conn.commit()
            
            return jsonify({
                'message': 'Player registered successfully',
                'player_id': player_id
            }), 201
            
        except Exception as e:
            conn.rollback()
            # Clean up uploaded file if database operation fails
            if os.path.exists(photo_path):
                os.remove(photo_path)
            raise e
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/players/<int:player_id>', methods=['DELETE'])
def delete_player(player_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Get photo path before deletion
            cur.execute("SELECT photo_path FROM players WHERE id = %s", (player_id,))
            result = cur.fetchone()
            
            if not result:
                return jsonify({'error': 'Player not found'}), 404
                
            photo_path = result[0]
            
            # Delete player data
            cur.execute("DELETE FROM players WHERE id = %s", (player_id,))
            
            # Delete associated consent records
            cur.execute("DELETE FROM consent_records WHERE player_id = %s", (player_id,))
            
            # Delete associated retention records
            cur.execute("DELETE FROM data_retention WHERE player_id = %s", (player_id,))
            
            conn.commit()
            
            # Delete photo file
            if os.path.exists(photo_path):
                os.remove(photo_path)
                
            return jsonify({'message': 'Player data deleted successfully'}), 200
            
        except Exception as e:
            conn.rollback()
            raise e
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/players/<int:player_id>/consent', methods=['GET'])
def get_consent_status(player_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cur.execute("""
                SELECT cr.*, p.full_name 
                FROM consent_records cr
                JOIN players p ON p.id = cr.player_id
                WHERE cr.player_id = %s
                ORDER BY cr.consent_date DESC
            """, (player_id,))
            
            consent_records = cur.fetchall()
            
            if not consent_records:
                return jsonify({'error': 'No consent records found'}), 404
                
            return jsonify({
                'player_name': consent_records[0]['full_name'],
                'consent_history': consent_records
            }), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 