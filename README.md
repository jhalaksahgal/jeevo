# 🌿 Jeevo

> An AI-powered multilingual healthcare assistant designed to provide accessible, reliable, and intelligent healthcare support through WhatsApp.

Jeevo combines Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), Speech Recognition, Computer Vision, Environmental Monitoring, and Healthcare Knowledge to deliver accurate medical assistance in multiple Indian languages. The platform is designed to bridge the healthcare accessibility gap by enabling users to interact naturally through text, voice, and images.

---

## 🚀 Features

- 🌍 Multilingual Support (10 Indian Languages)
- 🎤 Speech-to-Text using OpenAI Whisper
- 🖼️ Image OCR & Vision AI
- 🧠 Medical Retrieval-Augmented Generation (RAG)
- 💊 Medicine & Health Information
- 👶 Child Vaccination Tracking
- 🏥 Nearby Hospital Finder
- 📍 Anganwadi Center Locator
- 🌦️ Live Weather & AQI Monitoring
- 🚨 Automated Health Risk Alerts
- 👨‍👩‍👧 Family Health Management
- 💬 WhatsApp Cloud API Integration
- 🔒 AI Safety Validation & Medical Guardrails
- 📈 Regional Epidemic Monitoring

---

# 🏗️ System Architecture

```
                     User
                       │
                       ▼
              WhatsApp Cloud API
                       │
                       ▼
                 FastAPI Backend
                       │
      ┌───────────────────────────────────┐
      │      Intelligent Orchestrator     │
      └───────────────────────────────────┘
         │        │         │         │
         ▼        ▼         ▼         ▼
   Medical RAG  Whisper   Vision AI  Translation
         │
         ▼
    ChromaDB + Medical Knowledge Base
         │
         ▼
 Weather │ AQI │ Vaccine │ Hospital │ Anganwadi
```

---

# 🛠️ Tech Stack

## Backend

- FastAPI
- Python
- SQLAlchemy
- PostgreSQL
- Redis

## AI & Machine Learning

- OpenAI Whisper
- ChromaDB
- Sentence Transformers
- Groq/OpenAI LLMs
- Retrieval-Augmented Generation (RAG)

## APIs

- WhatsApp Cloud API
- Google Maps API
- OpenWeather API

## Database

- PostgreSQL
- Redis
- ChromaDB (Vector Database)

---

# 📌 Core Functionalities

## 🩺 AI Medical Assistance

- AI-powered symptom analysis
- Medical information retrieval
- Medication guidance
- First-aid recommendations
- Safe healthcare responses using RAG

---

## 🎤 Voice Assistant

- Voice note support
- Automatic speech transcription
- Audio-based conversations
- Multilingual speech interaction

---

## 🖼️ Vision AI

- Prescription OCR
- Medical image understanding
- Vision-based healthcare assistance

---

## 👶 Child Healthcare

- Vaccination schedule tracking
- Vaccine reminders
- Family profile management

---

## 📍 Smart Location Services

- Nearby hospitals
- Anganwadi center discovery
- Location-aware healthcare recommendations

---

## 🌦 Environmental Intelligence

- Weather monitoring
- Air Quality Index (AQI)
- Heatwave detection
- Regional disease outbreak monitoring

---

## 🚨 Smart Risk Alerts

- Pollution alerts
- Heatwave notifications
- Disease outbreak alerts
- Personalized health risk assessment

---

# 📂 Project Structure

```
jeevo/
│
├── app/
│   ├── ai/
│   ├── config/
│   ├── database/
│   ├── locales/
│   ├── logic/
│   ├── models/
│   ├── resources/
│   ├── routes/
│   ├── services/
│   └── utils/
│
├── medical_rag/
│   ├── documents/
│   ├── rag_engine.py
│   └── vector_store.py
│
├── tests/
│
├── vector_db/
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# 🌐 Supported Languages

Jeevo currently supports healthcare conversations in:

- 🇮🇳 Hindi
- 🇬🇧 English
- 🇧🇩 Bengali
- 🇮🇳 Gujarati
- 🇮🇳 Kannada
- 🇮🇳 Malayalam
- 🇮🇳 Marathi
- 🇮🇳 Punjabi
- 🇮🇳 Tamil
- 🇮🇳 Telugu

---

# 🔒 AI Safety & Reliability

Healthcare systems require trustworthy responses. Jeevo incorporates multiple safeguards including:

- Retrieval-Augmented Generation (RAG)
- Semantic Validation Engine
- Medical Source Verification
- Clinical Guardrails
- AI-generated Medical Disclaimers
- Emergency Escalation Logic
- Human-safe Response Validation

---

# ⚙️ Installation

## Clone the Repository

```bash
git clone https://github.com/<your-username>/jeevo.git

cd jeevo
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Configure Environment Variables

Create a `.env` file in the project root.

```env
DATABASE_URL=

OPENAI_API_KEY=

GROQ_API_KEY=

WHATSAPP_TOKEN=

GOOGLE_MAPS_API_KEY=

OPENWEATHER_API_KEY=

REDIS_URL=
```

## Run the Application

```bash
uvicorn app.main:app --reload
```

---

# 🧪 Running Tests

```bash
pytest
```

---

# 📖 Complete Workflow

Jeevo provides an end-to-end healthcare workflow:

- User onboarding
- Language detection
- Voice processing
- AI medical consultation
- Environmental monitoring
- Vaccination management
- Anganwadi discovery
- Nearby hospital search
- OCR-based prescription reading
- Multilingual AI responses
- Personalized health alerts

---

# 🌟 Highlights

- AI-powered multilingual healthcare assistant
- End-to-end WhatsApp automation
- Retrieval-Augmented Generation (RAG)
- Voice + Text + Image support
- Medical knowledge grounded using ChromaDB
- Automated environmental health monitoring
- Real-time personalized healthcare recommendations
- Modular and scalable FastAPI architecture

---

# 🚀 Future Improvements

- Electronic Health Records (EHR)
- Telemedicine Integration
- Doctor Appointment Booking
- Wearable Device Support
- Offline AI Assistance
- Predictive Disease Analytics
- Mobile Application

---

# 🤝 Contributing

Contributions are welcome!

1. Fork the repository.
2. Create a new feature branch.

```bash
git checkout -b feature-name
```

3. Commit your changes.

```bash
git commit -m "Added new feature"
```

4. Push your branch.

```bash
git push origin feature-name
```

5. Open a Pull Request.

---

# 📄 License

This project is licensed under the **MIT License**.

---

# 🏆 Acknowledgement

This project was developed as part of the **Health Hackathon**, conducted in collaboration with **Johns Hopkins University**. It showcases the application of Artificial Intelligence, Retrieval-Augmented Generation (RAG), multimodal AI, and healthcare technologies to build an intelligent, multilingual healthcare assistant aimed at improving healthcare accessibility for underserved communities.

---

# 👨‍💻 Author

Developed with ❤️ to make healthcare more accessible through AI.