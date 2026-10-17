Chance | Fixing How People Meet
Chance is a modern, web-based connection and dating platform designed to reduce swiping burnout and foster genuine conversations. It matches users based on mutual attraction, age proximity, location, and communication style, while offering robust privacy controls and real-time private messaging.

🚀 Key Features
Smart Matching Algorithm: Actively calculates age differences to prioritize users closest to your age, followed by shared cities and matching communication styles.

Anti-Burnout Feed: Profile pictures are blurred by default until you mutually connect, reducing superficial swiping fatigue.

Secure Authentication: Full sign-up and login system with encrypted passwords using bcrypt.

Profile Management: Upload real profile pictures, set your "Disclosure Tone" (Warm, Neutral, Playful), and write a personal bio.

Connection System: Send chat invitations that the receiver can freely Accept, Decline, or Block.

Private Message Hub: A dedicated, real-time chat interface that only unlocks after a mutual connection is established.

Admin Excel Sync: Automatically exports the active user database to a Users_Database.xlsx file in real-time using Pandas.

Wellbeing Check-ins: Users can log relationship success milestones and safe meetup outcomes.

🛠️ Tech Stack
Backend

Python 3.x

FastAPI (High-performance web framework)

SQLAlchemy (ORM mapped to an SQLite database)

Uvicorn (ASGI web server)

Pandas & OpenPyXL (Automated Excel database syncing)

Python-Multipart (Handling image uploads)

Bcrypt (Password hashing)

Frontend

HTML5 & Vanilla JavaScript (Single-page application logic)

Tailwind CSS (Utility-first styling via CDN)
