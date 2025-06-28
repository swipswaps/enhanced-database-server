#!/usr/bin/env python3
"""
Enhanced Database Management Server for KDE Memory Guardian
WHO: Users who want superior database tools with excellent UX
WHAT: Multi-database web interface with Adminer integration and enhanced features
WHY: Better than ncurses - professional web interface with all database tools
HOW: Flask server with Adminer, custom tools, and enhanced clipboard integration
"""

import os
import sys
import json
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, send_file, redirect
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration
BASE_DIR = Path(__file__).parent
CLIPBOARD_DB = Path.home() / '.clipboard_manager.db'
ADMINER_PATH = BASE_DIR / 'adminer.php'

class DatabaseManager:
    def __init__(self):
        self.databases = {
            'clipboard': {
                'path': str(CLIPBOARD_DB),
                'type': 'sqlite',
                'description': 'Clipboard Manager Database',
                'tables': ['clipboard_entries']
            }
        }
    
    def get_database_info(self, db_name):
        """Get database information"""
        if db_name not in self.databases:
            return None
        
        db_info = self.databases[db_name].copy()
        if db_info['type'] == 'sqlite' and os.path.exists(db_info['path']):
            try:
                conn = sqlite3.connect(db_info['path'])
                cursor = conn.execute("SELECT COUNT(*) FROM clipboard_entries")
                db_info['entry_count'] = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                db_info['tables'] = [row[0] for row in cursor.fetchall()]
                
                # Get database size
                db_info['size_bytes'] = os.path.getsize(db_info['path'])
                conn.close()
            except Exception as e:
                db_info['error'] = str(e)
        
        return db_info
    
    def execute_query(self, db_name, query, params=None):
        """Execute SQL query safely"""
        if db_name not in self.databases:
            return {'error': 'Database not found'}
        
        db_info = self.databases[db_name]
        if db_info['type'] != 'sqlite':
            return {'error': 'Only SQLite supported currently'}
        
        try:
            conn = sqlite3.connect(db_info['path'])
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.execute(query, params or [])
            
            if query.strip().upper().startswith('SELECT'):
                results = [dict(row) for row in cursor.fetchall()]
                return {'success': True, 'data': results, 'count': len(results)}
            else:
                conn.commit()
                return {'success': True, 'affected_rows': cursor.rowcount}
        except Exception as e:
            return {'error': str(e)}
        finally:
            if 'conn' in locals():
                conn.close()

db_manager = DatabaseManager()

# HTML Templates
MAIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced Database Manager - KDE Memory Guardian</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .card { box-shadow: 0 8px 32px rgba(0,0,0,0.1); border: none; }
        .navbar { background: rgba(255,255,255,0.95) !important; backdrop-filter: blur(10px); }
        .btn-primary { background: linear-gradient(45deg, #667eea, #764ba2); border: none; }
        .table-container { max-height: 400px; overflow-y: auto; }
        .query-editor { font-family: 'Courier New', monospace; }
        .status-badge { font-size: 0.8em; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-database me-2"></i>Enhanced Database Manager
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/adminer" target="_blank">
                    <i class="fas fa-external-link-alt me-1"></i>Adminer
                </a>
                <a class="nav-link" href="/api/docs">
                    <i class="fas fa-book me-1"></i>API Docs
                </a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="row">
            <div class="col-md-4">
                <div class="card mb-4">
                    <div class="card-header">
                        <h5><i class="fas fa-server me-2"></i>Database Overview</h5>
                    </div>
                    <div class="card-body" id="database-overview">
                        <div class="text-center">
                            <div class="spinner-border" role="status"></div>
                            <p class="mt-2">Loading databases...</p>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-tools me-2"></i>Quick Tools</h5>
                    </div>
                    <div class="card-body">
                        <div class="d-grid gap-2">
                            <button class="btn btn-primary" onclick="openAdminer()">
                                <i class="fas fa-database me-2"></i>Open Adminer
                            </button>
                            <button class="btn btn-outline-primary" onclick="exportDatabase()">
                                <i class="fas fa-download me-2"></i>Export Data
                            </button>
                            <button class="btn btn-outline-primary" onclick="showStats()">
                                <i class="fas fa-chart-bar me-2"></i>Statistics
                            </button>
                            <button class="btn btn-outline-primary" onclick="openClipboardUI()">
                                <i class="fas fa-clipboard me-2"></i>Clipboard UI
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-8">
                <div class="card mb-4">
                    <div class="card-header">
                        <h5><i class="fas fa-terminal me-2"></i>SQL Query Interface</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <select class="form-select" id="database-select">
                                <option value="clipboard">Clipboard Database</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <textarea class="form-control query-editor" id="sql-query" rows="4" 
                                placeholder="Enter your SQL query here...">SELECT * FROM clipboard_entries ORDER BY timestamp DESC LIMIT 10;</textarea>
                        </div>
                        <div class="d-flex gap-2">
                            <button class="btn btn-primary" onclick="executeQuery()">
                                <i class="fas fa-play me-2"></i>Execute Query
                            </button>
                            <button class="btn btn-outline-secondary" onclick="clearQuery()">
                                <i class="fas fa-eraser me-2"></i>Clear
                            </button>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-table me-2"></i>Query Results</h5>
                    </div>
                    <div class="card-body">
                        <div id="query-results">
                            <div class="text-muted text-center py-4">
                                <i class="fas fa-info-circle me-2"></i>Execute a query to see results
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Load database overview
        async function loadDatabaseOverview() {
            try {
                const response = await fetch('/api/databases');
                const databases = await response.json();
                
                let html = '';
                for (const [name, info] of Object.entries(databases)) {
                    const statusClass = info.error ? 'danger' : 'success';
                    const statusIcon = info.error ? 'exclamation-triangle' : 'check-circle';
                    
                    html += `
                        <div class="mb-3 p-3 border rounded">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h6 class="mb-0">${info.description || name}</h6>
                                <span class="badge bg-${statusClass}">
                                    <i class="fas fa-${statusIcon} me-1"></i>
                                    ${info.error ? 'Error' : 'Active'}
                                </span>
                            </div>
                            <small class="text-muted">
                                ${info.error || `${info.entry_count || 0} entries, ${(info.size_bytes/1024).toFixed(1)} KB`}
                            </small>
                        </div>
                    `;
                }
                
                document.getElementById('database-overview').innerHTML = html;
            } catch (error) {
                document.getElementById('database-overview').innerHTML = 
                    '<div class="alert alert-danger">Failed to load database info</div>';
            }
        }

        // Execute SQL query
        async function executeQuery() {
            const database = document.getElementById('database-select').value;
            const query = document.getElementById('sql-query').value.trim();
            
            if (!query) {
                alert('Please enter a SQL query');
                return;
            }

            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ database, query })
                });
                
                const result = await response.json();
                displayQueryResults(result);
            } catch (error) {
                displayQueryResults({ error: 'Network error: ' + error.message });
            }
        }

        // Display query results
        function displayQueryResults(result) {
            const container = document.getElementById('query-results');
            
            if (result.error) {
                container.innerHTML = `<div class="alert alert-danger">${result.error}</div>`;
                return;
            }

            if (result.data && result.data.length > 0) {
                const columns = Object.keys(result.data[0]);
                let html = `
                    <div class="table-responsive table-container">
                        <table class="table table-striped table-hover">
                            <thead class="table-dark">
                                <tr>${columns.map(col => `<th>${col}</th>`).join('')}</tr>
                            </thead>
                            <tbody>
                `;
                
                result.data.forEach(row => {
                    html += '<tr>';
                    columns.forEach(col => {
                        let value = row[col];
                        if (typeof value === 'string' && value.length > 100) {
                            value = value.substring(0, 100) + '...';
                        }
                        html += `<td>${value || ''}</td>`;
                    });
                    html += '</tr>';
                });
                
                html += `
                            </tbody>
                        </table>
                    </div>
                    <div class="mt-2 text-muted">
                        <i class="fas fa-info-circle me-1"></i>
                        ${result.count} rows returned
                    </div>
                `;
                
                container.innerHTML = html;
            } else if (result.success) {
                container.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check me-2"></i>
                        Query executed successfully. ${result.affected_rows || 0} rows affected.
                    </div>
                `;
            } else {
                container.innerHTML = '<div class="alert alert-info">No results returned</div>';
            }
        }

        // Utility functions
        function clearQuery() {
            document.getElementById('sql-query').value = '';
        }

        function openAdminer() {
            window.open('/adminer', '_blank');
        }

        function exportDatabase() {
            window.open('/api/export/clipboard', '_blank');
        }

        function showStats() {
            document.getElementById('sql-query').value = 
                'SELECT content_type, COUNT(*) as count, AVG(size_bytes) as avg_size FROM clipboard_entries GROUP BY content_type;';
        }

        function openClipboardUI() {
            window.open('http://localhost:3000', '_blank');
        }

        // Load data on page load
        document.addEventListener('DOMContentLoaded', loadDatabaseOverview);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main dashboard"""
    return render_template_string(MAIN_TEMPLATE)

@app.route('/api/databases')
def get_databases():
    """Get database information"""
    result = {}
    for name in db_manager.databases:
        result[name] = db_manager.get_database_info(name)
    return jsonify(result)

@app.route('/api/query', methods=['POST'])
def execute_query():
    """Execute SQL query"""
    data = request.get_json()
    database = data.get('database', 'clipboard')
    query = data.get('query', '')
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    result = db_manager.execute_query(database, query)
    return jsonify(result)

@app.route('/api/export/<database>')
def export_database(database):
    """Export database as JSON"""
    if database not in db_manager.databases:
        return jsonify({'error': 'Database not found'}), 404
    
    result = db_manager.execute_query(database, 'SELECT * FROM clipboard_entries ORDER BY timestamp DESC')
    if result.get('error'):
        return jsonify(result), 500
    
    return jsonify({
        'database': database,
        'exported_at': time.time(),
        'count': len(result['data']),
        'data': result['data']
    })

@app.route('/adminer')
def adminer_redirect():
    """Redirect to Adminer with SQLite database"""
    if not ADMINER_PATH.exists():
        return "Adminer not found. Please ensure adminer.php is in the database-tools directory.", 404
    
    # Start PHP built-in server for Adminer if not running
    start_php_server()
    return redirect('http://localhost:8080/adminer.php?sqlite=' + str(CLIPBOARD_DB))

@app.route('/api/docs')
def api_docs():
    """API documentation"""
    docs = {
        'title': 'Enhanced Database Manager API',
        'version': '1.0.0',
        'endpoints': {
            'GET /': 'Main dashboard interface',
            'GET /api/databases': 'Get database information',
            'POST /api/query': 'Execute SQL query',
            'GET /api/export/<database>': 'Export database as JSON',
            'GET /adminer': 'Access Adminer interface',
            'GET /api/docs': 'This documentation'
        },
        'examples': {
            'query': {
                'url': '/api/query',
                'method': 'POST',
                'body': {
                    'database': 'clipboard',
                    'query': 'SELECT * FROM clipboard_entries LIMIT 10'
                }
            }
        }
    }
    return jsonify(docs)

def start_php_server():
    """Start PHP built-in server for Adminer"""
    def run_php():
        try:
            subprocess.run([
                'php', '-S', 'localhost:8080', '-t', str(BASE_DIR)
            ], capture_output=True)
        except:
            pass
    
    # Start in background thread
    threading.Thread(target=run_php, daemon=True).start()

if __name__ == '__main__':
    print("🗃️ Enhanced Database Manager for KDE Memory Guardian")
    print("=" * 60)
    print(f"📊 Main Interface: http://localhost:5000")
    print(f"🗄️ Adminer Access: http://localhost:5000/adminer")
    print(f"📚 API Documentation: http://localhost:5000/api/docs")
    print(f"📋 Clipboard Database: {CLIPBOARD_DB}")
    print("=" * 60)
    
    # Check if clipboard database exists
    if CLIPBOARD_DB.exists():
        print(f"✅ Clipboard database found ({CLIPBOARD_DB.stat().st_size} bytes)")
    else:
        print("⚠️ Clipboard database not found - will be created when first used")
    
    # Check if Adminer exists
    if ADMINER_PATH.exists():
        print(f"✅ Adminer ready ({ADMINER_PATH.stat().st_size} bytes)")
    else:
        print("⚠️ Adminer not found - download from https://www.adminer.org/")
    
    print("\n🚀 Starting enhanced database server...")
    app.run(host='0.0.0.0', port=5000, debug=False)
