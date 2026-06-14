# 🎓 NSDCP — Nigerian Student Digital Community Platform

A **secure, moderated civic platform** for Nigerian students featuring controlled content, group governance, real-time chat, and privacy-first design.

---

## 🔐 Core Safety Architecture

| Safety Feature | How it works |
|---|---|
| **Post moderation** | No post visible without admin approval |
| **Privacy display** | Only "First Name from School" shown publicly |
| **Group trust levels** | New → Verified → Trusted / Flagged |
| **Invitation-only groups** | No open membership; explicit invite required |
| **Vote locking** | Max 3 vote changes, then permanently locked |
| **Data encryption** | NIN and School Reg encrypted with Fernet |
| **Admin activity log** | Every admin action is logged |
| **Trust levels** | Users: New → Verified → Trusted |

---

## 📁 Project Structure

```
nsdcp/
├── app.py            # Flask factory + SocketIO + blueprint registration
├── models.py         # 15 database models (User, Post, Group, Message, etc.)
├── auth.py           # Register, login, profile, edit
├── main.py           # Dashboard, search, notifications
├── posts.py          # Post submit, moderation, comments, likes
├── polls.py          # Poll CRUD + 3-change vote lock system
├── chat.py           # Private + group SocketIO real-time chat
├── groups.py         # Group create, invite, trust system
├── friends.py        # Connect, block, unfriend
├── admin.py          # Full admin panel (posts, users, groups, reports, logs)
├── requirements.txt
├── Procfile          # Railway/Render start command
├── railway.toml
├── runtime.txt
├── .env.example
├── templates/        # 27 Jinja2 templates
│   ├── base.html
│   ├── index.html / login.html / register.html / dashboard.html
│   ├── profile.html / edit_profile.html / search.html / friends.html
│   ├── post.html / create_post.html
│   ├── polls.html / poll_detail.html / create_poll.html
│   ├── chat/         inbox.html, conversation.html
│   ├── group/        index.html, create.html, chat.html
│   └── admin/        dashboard, posts, users, user_detail, groups, reports, broadcast, logs
└── static/
    ├── css/style.css  (42KB — deep green + gold Nigerian civic aesthetic)
    └── uploads/
```

---

## ⚙️ Local Setup

```bash
git clone <your-repo>
cd nsdcp
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD, FERNET_KEY
python app.py
```

Visit: **http://localhost:5000**

Default admin: `admin@nsdcp.ng` / `Admin@NSDCP2025`

---

## 🚂 Deploy to Railway

1. Push to GitHub
2. Railway → New Project → Deploy from GitHub
3. Add a **PostgreSQL** plugin
4. Set environment variables:

```env
SECRET_KEY=<long random string>
DATABASE_URL=<Railway PostgreSQL URL — auto-filled if plugin added>
ADMIN_EMAIL=admin@nsdcp.ng
ADMIN_PASSWORD=<your secure password>
FERNET_KEY=<generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
```

Railway reads `Procfile` and deploys automatically.

---

## 🌐 Deploy to Render

1. New Web Service → Connect GitHub
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn --worker-class eventlet -w 1 'app:create_app()' --bind 0.0.0.0:$PORT`
4. Add same env vars as above
5. Add a PostgreSQL database and paste URL into `DATABASE_URL`

---

## 👑 Role Hierarchy

| Role | Can Post | Approve Posts | Manage Users | Create Polls |
|---|---|---|---|---|
| Admin | ✅ (auto-approved) | ✅ | ✅ | ✅ |
| President | ✅ (pending review) | ❌ | ❌ | ❌ |
| Vice President | ✅ (pending review) | ❌ | ❌ | ❌ |
| Representative | ✅ (pending review) | ❌ | ❌ | ❌ |
| Student | ❌ | ❌ | ❌ | ❌ |

---

## 🛡️ Trust Level System

### Users
- **New** — limited actions, cannot post or add friends without verification
- **Verified** — full access after admin verification
- **Trusted** — higher privileges, set manually by admin
- **Flagged** — under review, restricted

### Groups
- **New** — restricted visibility, not discoverable
- **Verified** — visible in Discover section
- **Trusted** — featured group
- **Flagged** — under admin investigation

---

## 🗳️ Voting Rules

1. Each user gets **1 vote** per poll
2. Users can **change their vote up to 3 times**
3. After 3 changes → vote is **permanently locked** (no further changes)
4. Admin sets poll expiry date/time
5. Admin can show live results or end-only results

---

## 💬 Comment Privacy

All comments display as:
> **"Amina from FUTB"** — not full name, not contact info

This protects user privacy while enabling academic discussion.

---

## 🔒 Data Protection

- Passwords: `bcrypt` hash (never stored plaintext)
- NIN + School Reg: `Fernet` symmetric encryption
- Public display: First name + school only
- NIN never displayed publicly — admin only sees "provided/not provided"
- Admin action log: all changes tracked with actor, target, timestamp

---

## 🆘 Support

Contact: admin@nsdcp.ng
