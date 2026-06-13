# Deploying SafeSight backend on AWS (EC2 + RDS Postgres)

Single EC2 VM running **daphne** behind **nginx**, with **RDS Postgres** as the
database. Files referenced here live in `deploy/`.

## 1. Provision

**RDS Postgres**
- Create a PostgreSQL instance (db.t3.micro is fine for a demo).
- DB name `safesight`, note the master user/password and endpoint host.
- Security group: allow inbound TCP **5432** *from the EC2 instance's security
  group only* (not the public internet).

**EC2**
- Ubuntu 22.04/24.04, **t3.medium or larger** (the torch + dlib ML stack needs
  ~2 GB RAM; t3.micro/small will OOM).
- 20 GB+ disk.
- Security group: allow inbound **22** (SSH, your IP), **80** (HTTP), **443**
  (HTTPS).

## 2. Server setup (SSH into the EC2 box)

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx \
  build-essential cmake libpq-dev libgl1 libglib2.0-0
# build-essential + cmake are required to compile dlib (face-recognition).
# libgl1/libglib2.0-0 are required by OpenCV/ultralytics at runtime.

git clone https://github.com/momenawab/Backendgrad.git safesight-backend
cd safesight-backend

python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
# CPU-only torch so you don't pull multi-GB CUDA wheels:
pip install torch==2.5.1 torchvision==0.20.1 \
  --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## 3. Configure environment

```bash
cp .env.example .env
nano .env          # fill in SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL, etc.
```

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 4. Migrate, collect static, create admin

```bash
set -a; source .env; set +a        # load env into the shell
python manage.py migrate
python manage.py collectstatic --no-input
python manage.py createsuperuser
```

## 5. Run daphne as a service

```bash
sudo cp deploy/safesight.service /etc/systemd/system/safesight.service
# edit User/paths inside if you didn't use /home/ubuntu/safesight-backend
sudo systemctl daemon-reload
sudo systemctl enable --now safesight
sudo systemctl status safesight        # should be "active (running)"
journalctl -u safesight -f             # live logs
```

## 6. nginx reverse proxy

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/safesight
sudo ln -s /etc/nginx/sites-available/safesight /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
# set server_name in the file to your domain / EC2 public DNS
sudo nginx -t && sudo systemctl reload nginx
```

Visit `http://<ec2-public-dns>/admin/` — you should get the Django admin login.

## 7. HTTPS (recommended, required for wss:// from the app)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
```

## Redeploying after a push

```bash
cd ~/safesight-backend
git pull
source venv/bin/activate
pip install -r requirements.txt          # only if deps changed
python manage.py migrate
python manage.py collectstatic --no-input
sudo systemctl restart safesight
```

## Notes / caveats
- **WebSockets:** routed via nginx `/ws/` (`ws/detect/`, `ws/notifications/`).
  With HTTPS, the Flutter app must use `wss://`.
- **Channel layer is in-memory** — run a single daphne process. To scale to
  multiple workers/instances, switch to `channels-redis` + ElastiCache Redis.
- **Model files** (`graduation_project 2/best (4).pt`, the face joblib) are in
  the repo, so they arrive with `git clone`. No extra download needed.
- **dlib build is slow** and memory-hungry; if it fails, give the instance more
  RAM or add swap during the build.

## Flutter app
Point the base URL at `https://<your-domain>` and WebSockets at
`wss://<your-domain>`. No other app changes.
