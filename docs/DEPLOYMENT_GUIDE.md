# Hostel Management System (HMS) — Production Deployment Guide
**Course:** BBAT104 - Fundamentals of Total Quality Management (TQM)  
**Academic Session:** 2026-27  
**Quality Goal:** Q05 — Reduce Response Time (< 10ms SLA)  
**Author:** Rohan Bakshi (Roll No: 2410301057)

---

## 1. Production Architecture Overview

The application follows an optimized **Modular Monolith** architecture:
- **Application Server:** FastAPI running on Uvicorn ASGI server.
- **Concurrency & State Model:** Single-worker or thread-pool process topology ensuring zero cache race conditions and optimal SQLite Write-Ahead Logging (WAL) concurrency.
- **Database Engine:** Embedded SQLite 3 with WAL journal mode, `synchronous = NORMAL`, and 64MB shared page cache (`cache_size = -64000`), delivering sub-millisecond query execution.
- **In-Memory Cache:** Centralized thread-safe LRU cache with tag-based invalidation delivering sub-0.05ms warm response times.
- **Reverse Proxy:** Nginx providing TLS termination, static asset compression (Gzip/Brotli), security headers, and rate limiting.

---

## 2. Docker Production Deployment

### 2.1 Production `.env` Setup
Create a production `.env` file with a strong random secret key:
```bash
# Generate a cryptographically strong 64-character secret
python -c "import secrets; print(secrets.token_hex(32))"
```

Configure `.env`:
```ini
APP_NAME="Hostel Management System Web App"
APP_ENV="production"
DEBUG=False
HOST="0.0.0.0"
PORT=8000
SECRET_KEY="e8f49a37c9b83b1287c9f83a4291de48a123c892837bc91028374a8b7c6d5e4f"
DATABASE_PATH="data/hostel_web.db"
ENABLE_SQLITE_WAL=True
```

### 2.2 Container Startup
```bash
docker-compose up -d --build
```

### 2.3 Container Health Monitoring
```bash
docker inspect --format='{{json .State.Health}}' hostel-management-system
```

---

## 3. Native Linux (Ubuntu/Debian) Systemd Deployment

### 3.1 System Directory & Permissions
```bash
sudo mkdir -p /var/www/hostel-web-app
sudo chown -R $USER:$USER /var/www/hostel-web-app
git clone https://github.com/RohanBakshi-04/TQM-Web-App.git /var/www/hostel-web-app
cd "/var/www/hostel-web-app/Hostel Management System Web App"

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3.2 Systemd Service Unit (`/etc/systemd/system/hostel-app.service`)
```ini
[Unit]
Description=Hostel Management System TQM Web Application
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/hostel-web-app/Hostel Management System Web App
Environment="PATH=/var/www/hostel-web-app/Hostel Management System Web App/venv/bin"
EnvironmentFile=/var/www/hostel-web-app/Hostel Management System Web App/.env
ExecStart=/var/www/hostel-web-app/Hostel Management System Web App/venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1

Restart=always
RestartSec=5s

# Security sandboxing
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable hostel-app.service
sudo systemctl start hostel-app.service
sudo systemctl status hostel-app.service
```

---

## 4. Reverse Proxy & SSL Configuration (Nginx)

### 4.1 Nginx Site Configuration (`/etc/nginx/sites-available/hostel.conf`)
```nginx
server {
    listen 80;
    server_name hostel.university.edu;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name hostel.university.edu;

    ssl_certificate /etc/letsencrypt/live/hostel.university.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hostel.university.edu/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' data: https://cdn.jsdelivr.net; img-src 'self' data:;" always;

    # Gzip Compression for sub-10ms assets
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }

    # Static file direct cache bypass
    location /static/ {
        alias /var/www/hostel-web-app/Hostel Management System Web App/frontend/;
        expires 7d;
        add_header Cache-Control "public, max-age=604800, immutable";
    }
}
```

---

## 5. Automated Backup & Maintenance Schedule

### 5.1 SQLite Online Backup Cron Job
Because the application uses SQLite WAL mode, hot backups can be taken without locking or interrupting active transactions using the built-in backup API.

Create a nightly backup script `/usr/local/bin/backup-hostel-db.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/hostel-system"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"

# Trigger hot SQLite backup
sqlite3 "/var/www/hostel-web-app/Hostel Management System Web App/data/hostel_web.db" ".backup '$BACKUP_DIR/backup_$TIMESTAMP.db'"

# Verify backup integrity
INTEGRITY=$(sqlite3 "$BACKUP_DIR/backup_$TIMESTAMP.db" "PRAGMA integrity_check;")
if [ "$INTEGRITY" == "ok" ]; then
    gzip "$BACKUP_DIR/backup_$TIMESTAMP.db"
    echo "Backup completed successfully at $TIMESTAMP"
else
    echo "Backup integrity check failed!" | mail -s "HMS Backup Alert" sysadmin@univ.edu
fi

# Retain 30 days of historical backups
find "$BACKUP_DIR" -name "backup_*.db.gz" -mtime +30 -delete
```

Add to cron:
```bash
0 2 * * * /usr/local/bin/backup-hostel-db.sh >> /var/log/hostel_backups.log 2>&1
```

---

## 6. Disaster Recovery & Rollback Procedure

1. **Stop Application Service:**
   ```bash
   sudo systemctl stop hostel-app.service
   ```
2. **Decompress Backup Snapshot:**
   ```bash
   gunzip -c /var/backups/hostel-system/backup_YYYYMMDD_HHMMSS.db.gz > /tmp/restore.db
   ```
3. **Verify Integrity of Restore Candidate:**
   ```bash
   sqlite3 /tmp/restore.db "PRAGMA integrity_check;"
   ```
4. **Replace Production Database:**
   ```bash
   mv /var/www/hostel-web-app/Hostel Management System Web App/data/hostel_web.db /var/www/hostel-web-app/Hostel Management System Web App/data/hostel_web.db.corrupt
   mv /tmp/restore.db /var/www/hostel-web-app/Hostel Management System Web App/data/hostel_web.db
   ```
5. **Restart Service:**
   ```bash
   sudo systemctl start hostel-app.service
   sudo systemctl status hostel-app.service
   ```
