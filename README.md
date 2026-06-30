# 🔗 LostLinks

LostLinks is a modern, responsive web application designed to help campus communities easily report and track lost and found items. By integrating an intuitive Bento Box interface with advanced mapping and an AI-powered assistant, LostLinks simplifies the recovery process for everyone.

##  Features

- **User Authentication:** Secure signup and login using Firebase/Supabase, complete with email verification.
- **Interactive Campus Mapping:** Precise location selection for lost and found items utilizing Leaflet.js.
- **Integrated Camera Capture:** Seamlessly capture photos directly from the browser to attach to item reports.
- **AI Assistant:** A deeply integrated, LangChain-powered AI assistant that helps users navigate the platform and search for items.
- **Dashboard & Profile Management:** Track your active and resolved listings, update statuses, and manage claimant resolution directly from a personalized dashboard.
- **Neumorphic & Modern Design:** A beautifully styled, responsive UI built with Tailwind CSS, supporting modern design tokens and micro-animations.

## 🛠️ Tech Stack

### Backend
- **Framework:** Flask (Python)
- **Database/Auth:** Supabase, Pyrebase4 (Firebase)
- **AI Integration:** LangChain, Google Generative AI (Gemini)

### Frontend
- **Templating:** HTML5 / Jinja2
- **Styling:** Tailwind CSS (compiled locally)
- **Mapping:** Leaflet.js
- **Interactivity:** Vanilla JavaScript

## 🚀 Getting Started

Follow these instructions to get a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

- Python 3.8+
- Node.js and npm (for Tailwind CSS)
- API Keys for Google Gemini, Supabase, and Firebase (configured in `.env`)

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/SumiRann1/LostLinks.git
   cd LostLinks
   ```

2. **Set up the Python Virtual Environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

3. **Install Backend Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Frontend Dependencies:**
   ```bash
   npm install
   ```

5. **Configure Environment Variables:**
   Create a `.env` file in the root directory and add your secret keys:
   ```env
   # Add your specific Firebase, Supabase, and Gemini API keys here
   # Example:
   GOOGLE_API_KEY=your_gemini_api_key
   ```

### Running the Application

1. **Build Tailwind CSS (Optional/Development):**
   If you make changes to the CSS or HTML classes, compile Tailwind using:
   ```bash
   npx tailwindcss -i ./static/css/input.css -o ./static/css/style.css --watch
   ```

2. **Start the Flask Server:**
   ```bash
   python main.py
   ```

3. **Access the Application:**
   Open your browser and navigate to `http://localhost:5000`.

## 📄 License

This project is licensed under the ISC License.
